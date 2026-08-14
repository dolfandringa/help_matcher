from typing import Any

from sqlmodel import Session, select

from help_matcher.geocoding import geocode_location
from help_matcher.models import Conversation, ConversationIntent, ConversationStatus, utc_now
from help_matcher.whatsapp.actions import get_or_create_user
from help_matcher.whatsapp.messages import IncomingWhatsAppMessage


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


def geocode_conversation_location(
    session: Session,
    conversation: Conversation,
    *,
    administrative_area_name: str | None = None,
    address_text: str | None = None,
) -> Conversation:
    """Geocode location fields and store GeoJSON in conversation state."""

    collected_administrative_area = administrative_area_name or conversation.collected_data.get("administrative_area_name")
    collected_address = address_text or conversation.collected_data.get("address_text")
    geometry = geocode_location(
        administrative_area_name=collected_administrative_area,
        address_text=collected_address,
    )
    return save_conversation_state(
        session,
        conversation,
        collected_data={
            "administrative_area_name": collected_administrative_area,
            "address_text": collected_address,
            "geometry": geometry,
        },
    )


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
    conversation.current_step = None
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
