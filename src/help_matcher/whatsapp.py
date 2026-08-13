"""Simple Python API for WhatsApp bot developers.

The bot developer should import these functions after they have parsed a
WhatsApp message into an action such as "create offer", "create demand", or
"close demand".

Every function takes a SQLModel ``Session`` and the sender's WhatsApp Business
Scoped User ID (BSUID). If the BSUID is unknown when creating an offer or
demand, the user is created automatically from the contact details supplied by
WhatsApp.

Example:

```python
from sqlmodel import Session

from help_matcher.database import engine
from help_matcher.whatsapp import create_demand

with Session(engine) as session:
    demand = create_demand(
        session,
        whatsapp_bsuid="123456789",
        original_message="Necesitamos agua y carpas en el barrio San Javier",
        whatsapp_name="Maria",
        phone_number="+573001112233",
        tags=["water", "shelter"],
        administrative_area_name="San Javier",
        administrative_area_level="barrio",
    )
```
"""

from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlmodel import Session, select

from help_matcher.config import Settings, get_settings
from help_matcher.models import (
    Conversation,
    ConversationIntent,
    ConversationStatus,
    Demand,
    Offer,
    RecordStatus,
    User,
    UserRole,
    utc_now,
)
from help_matcher.tags import link_tags


@dataclass(frozen=True)
class IncomingWhatsAppMessage:
    """A normalized text message extracted from a Meta WhatsApp webhook payload."""

    message_id: str
    from_bsuid: str
    text: str
    contact_name: str | None = None
    phone_number: str | None = None


def extract_text_messages(payload: dict[str, Any]) -> list[IncomingWhatsAppMessage]:
    """Extract text messages from a Meta WhatsApp webhook payload.

    Delivery/read events and non-text messages are ignored. Use ``from_bsuid``
    for user lookup and for replying to the incoming message.
    """

    extracted: list[IncomingWhatsAppMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts_by_id = {
                contact.get("wa_id"): contact
                for contact in value.get("contacts", [])
                if contact.get("wa_id")
            }
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                from_bsuid = message.get("from")
                message_id = message.get("id")
                text = message.get("text", {}).get("body")
                if not from_bsuid or not message_id or not text:
                    continue
                contact = contacts_by_id.get(from_bsuid, {})
                extracted.append(
                    IncomingWhatsAppMessage(
                        message_id=message_id,
                        from_bsuid=from_bsuid,
                        text=text,
                        contact_name=contact.get("profile", {}).get("name"),
                        phone_number=contact.get("wa_id"),
                    )
                )
    return extracted


def reply_to_message(
    incoming: IncomingWhatsAppMessage,
    text: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Reply to a specific incoming WhatsApp message.

    This intentionally only supports replies to incoming webhook messages, not
    unsolicited outbound messages.
    """

    current_settings = settings or get_settings()
    if not current_settings.meta_access_token:
        raise RuntimeError("META_ACCESS_TOKEN is not configured")
    if not current_settings.meta_phone_number_id:
        raise RuntimeError("META_PHONE_NUMBER_ID is not configured")

    url = (
        f"https://graph.facebook.com/{current_settings.meta_api_version}/"
        f"{current_settings.meta_phone_number_id}/messages"
    )
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {current_settings.meta_access_token}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": incoming.from_bsuid,
            "context": {"message_id": incoming.message_id},
            "type": "text",
            "text": {"preview_url": False, "body": text},
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_or_create_conversation(
    session: Session,
    incoming: IncomingWhatsAppMessage,
    *,
    intent: ConversationIntent = ConversationIntent.unknown,
    current_step: str | None = None,
) -> Conversation:
    """Return the active conversation for a WhatsApp user, creating one if needed."""

    user = get_or_create_user(
        session,
        whatsapp_bsuid=incoming.from_bsuid,
        whatsapp_name=incoming.contact_name,
        phone_number=incoming.phone_number,
    )
    conversation = session.exec(
        select(Conversation).where(
            Conversation.whatsapp_bsuid == incoming.from_bsuid,
            Conversation.status == ConversationStatus.active,
        )
    ).first()
    if conversation is None:
        conversation = Conversation(
            user_id=user.id,
            whatsapp_bsuid=incoming.from_bsuid,
            intent=intent,
            current_step=current_step,
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
    return record_incoming_message(session, conversation, incoming)


def record_incoming_message(
    session: Session,
    conversation: Conversation,
    incoming: IncomingWhatsAppMessage,
) -> Conversation:
    """Append an incoming user message to the conversation history."""

    conversation.last_message_id = incoming.message_id
    conversation.message_history = [
        *conversation.message_history,
        {"role": "user", "message_id": incoming.message_id, "text": incoming.text, "created_at": utc_now().isoformat()},
    ]
    conversation.updated_at = utc_now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def save_conversation_state(
    session: Session,
    conversation: Conversation,
    *,
    intent: ConversationIntent | None = None,
    current_step: str | None = None,
    collected_data: dict[str, Any] | None = None,
    llm_context_summary: str | None = None,
) -> Conversation:
    """Persist partial LLM/bot state while collecting enough data for an offer/demand."""

    if intent is not None:
        conversation.intent = intent
    if current_step is not None:
        conversation.current_step = current_step
    if collected_data is not None:
        conversation.collected_data = {**conversation.collected_data, **collected_data}
    if llm_context_summary is not None:
        conversation.llm_context_summary = llm_context_summary
    conversation.updated_at = utc_now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def record_bot_reply(
    session: Session,
    conversation: Conversation,
    *,
    text: str,
    meta_message_id: str | None = None,
) -> Conversation:
    """Append a bot reply to the conversation history after sending it."""

    conversation.message_history = [
        *conversation.message_history,
        {"role": "assistant", "message_id": meta_message_id, "text": text, "created_at": utc_now().isoformat()},
    ]
    conversation.updated_at = utc_now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def complete_conversation(session: Session, conversation: Conversation) -> Conversation:
    """Mark a conversation complete after creating its Demand or Offer."""

    conversation.status = ConversationStatus.completed
    conversation.completed_at = utc_now()
    conversation.updated_at = utc_now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def abandon_conversation(session: Session, conversation: Conversation) -> Conversation:
    """Mark a conversation abandoned when the user cancels or the bot gives up."""

    conversation.status = ConversationStatus.abandoned
    conversation.updated_at = utc_now()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def get_or_create_user(
    session: Session,
    *,
    whatsapp_bsuid: str,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
) -> User:
    """Return the user linked to ``whatsapp_bsuid``, creating one if needed.

    Args:
        session: Open SQLModel database session.
        whatsapp_bsuid: WhatsApp Business Scoped User ID for the sender.
        whatsapp_name: Optional display/profile name supplied by WhatsApp.
        phone_number: Optional phone number supplied by WhatsApp.

    Returns:
        The existing or newly-created regular ``User``.

    Notes:
        Existing users are updated only when WhatsApp provides a name or phone
        number and the stored value is still empty.
    """

    user = session.exec(select(User).where(User.whatsapp_bsuid == whatsapp_bsuid)).first()
    if user is not None:
        changed = False
        if whatsapp_name and not user.name:
            user.name = whatsapp_name
            changed = True
        if phone_number and not user.phone_number:
            user.phone_number = phone_number
            changed = True
        if changed:
            user.updated_at = utc_now()
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    user = User(
        whatsapp_bsuid=whatsapp_bsuid,
        name=whatsapp_name,
        phone_number=phone_number,
        role=UserRole.user,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_offer(
    session: Session,
    *,
    whatsapp_bsuid: str,
    original_message: str,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
    tags: list[str] | None = None,
    location_text: str | None = None,
    administrative_area_name: str | None = None,
    administrative_area_level: str | None = None,
    address_text: str | None = None,
) -> Offer:
    """Create an ``Offer`` from a WhatsApp conversation.

    Use this when the bot determines that a user wants to provide help.
    ``original_message`` should be the raw message or concise original help
    text that led to the offer. ``tags`` should contain normalized help
    categories extracted by the bot, for example ``["water", "transport"]``.
    """

    user = get_or_create_user(
        session,
        whatsapp_bsuid=whatsapp_bsuid,
        whatsapp_name=whatsapp_name,
        phone_number=phone_number,
    )
    offer = Offer(
        user_id=user.id,
        original_message=original_message,
        phone_number=phone_number or user.phone_number,
        location_text=location_text,
        administrative_area_name=administrative_area_name,
        administrative_area_level=administrative_area_level,
        address_text=address_text,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)
    link_tags(session, offer, tags or [])
    return offer


def create_demand(
    session: Session,
    *,
    whatsapp_bsuid: str,
    original_message: str,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
    tags: list[str] | None = None,
    location_text: str | None = None,
    administrative_area_name: str | None = None,
    administrative_area_level: str | None = None,
    address_text: str | None = None,
) -> Demand:
    """Create a ``Demand`` from a WhatsApp conversation.

    Use this when the bot determines that a user needs help. Location fields
    are optional but should be filled when the bot can extract them:
    ``administrative_area_name`` could be a barrio or municipality, while
    ``address_text`` should be a specific address or landmark.
    """

    user = get_or_create_user(
        session,
        whatsapp_bsuid=whatsapp_bsuid,
        whatsapp_name=whatsapp_name,
        phone_number=phone_number,
    )
    demand = Demand(
        user_id=user.id,
        original_message=original_message,
        phone_number=phone_number or user.phone_number,
        location_text=location_text,
        administrative_area_name=administrative_area_name,
        administrative_area_level=administrative_area_level,
        address_text=address_text,
    )
    session.add(demand)
    session.commit()
    session.refresh(demand)
    link_tags(session, demand, tags or [])
    return demand


def close_offer(session: Session, *, whatsapp_bsuid: str, offer_id: int) -> Offer:
    """Close an offer created by the WhatsApp user.

    Raises ``HTTPException(404)`` if the BSUID is unknown, the offer does not
    exist, or the offer belongs to another user.
    """

    user = _get_user_or_404(session, whatsapp_bsuid)
    offer = session.get(Offer, offer_id)
    if offer is None or offer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    offer.status = RecordStatus.closed
    offer.closed_at = utc_now()
    offer.updated_at = utc_now()
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return offer


def close_demand(session: Session, *, whatsapp_bsuid: str, demand_id: int) -> Demand:
    """Close a demand created by the WhatsApp user.

    Raises ``HTTPException(404)`` if the BSUID is unknown, the demand does not
    exist, or the demand belongs to another user.
    """

    user = _get_user_or_404(session, whatsapp_bsuid)
    demand = session.get(Demand, demand_id)
    if demand is None or demand.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    demand.status = RecordStatus.closed
    demand.closed_at = utc_now()
    demand.updated_at = utc_now()
    session.add(demand)
    session.commit()
    session.refresh(demand)
    return demand


def _get_user_or_404(session: Session, whatsapp_bsuid: str) -> User:
    user = session.exec(select(User).where(User.whatsapp_bsuid == whatsapp_bsuid)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp user not found")
    return user
