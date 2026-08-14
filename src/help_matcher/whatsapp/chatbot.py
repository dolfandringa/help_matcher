import re
from typing import Any, Literal

from sqlmodel import Session, select

from help_matcher.models import Conversation, ConversationIntent, Demand, DemandUser, Offer, OfferUser, RecordStatus, User
from help_matcher.whatsapp.actions import close_demand_by_public_id, close_offer_by_public_id, create_demand, create_offer
from help_matcher.whatsapp.conversations import (
    complete_conversation,
    geocode_conversation_location,
    get_or_create_conversation,
    record_bot_reply,
    save_conversation_state,
)
from help_matcher.whatsapp.messages import IncomingWhatsAppMessage

RecordKind = Literal["demand", "offer"]

REQUIRED_FIELDS = ("intent", "original_message", "title", "tags", "location")
YES_WORDS = {"yes", "y", "si", "sí", "correcto", "confirmo", "ok", "dale"}
NO_WORDS = {"no", "cancel", "cancelar", "espera"}


def llm_interpret_user_message(conversation: Conversation, incoming: IncomingWhatsAppMessage) -> dict[str, Any]:
    """Placeholder for LLM extraction of intent, fields, and completeness."""

    text = incoming.text.strip()
    lower_text = text.lower()
    data: dict[str, Any] = {"original_message": text, "title": text[:200]}
    if any(word in lower_text for word in ("ofrezco", "tengo", "puedo ayudar", "donar", "disponible")):
        data["intent"] = "offer"
    elif any(word in lower_text for word in ("necesito", "necesitamos", "ayuda", "urgente", "falta")):
        data["intent"] = "demand"
    elif conversation.intent != ConversationIntent.unknown:
        data["intent"] = conversation.intent.value
    data["tags"] = _extract_placeholder_tags(lower_text)
    location = _extract_placeholder_location(text)
    if location:
        data.update(location)
    return data


def llm_review_completed_fields(conversation: Conversation) -> dict[str, Any]:
    """Placeholder for final LLM review over the full user-provided text."""

    user_messages = [message["text"] for message in conversation.message_history if message.get("role") == "user"]
    if not user_messages:
        return {}
    return {"original_message": "\n".join(user_messages), "title": user_messages[-1][:200]}


def llm_next_question(missing_fields: list[str]) -> str:
    """Placeholder for LLM-generated follow-up questions."""

    if "intent" in missing_fields:
        return "¿Necesitas ayuda o estás ofreciendo ayuda?"
    if "location" in missing_fields:
        return "¿En qué barrio, corregimiento, municipio o dirección es?"
    if "tags" in missing_fields:
        return "¿Qué tipo de ayuda es? Por ejemplo agua, comida, rescate, transporte, albergue o maquinaria."
    return "¿Puedes darme un poco más de información?"


def llm_summary_message(conversation: Conversation) -> str:
    """Placeholder for LLM-generated confirmation summary."""

    data = conversation.collected_data
    record_label = "oferta" if data.get("intent") == "offer" else "solicitud de ayuda"
    location = data.get("address_text") or data.get("administrative_area_name") or "sin ubicación"
    tags = ", ".join(data.get("tags", [])) or "sin etiquetas"
    return (
        f"Voy a registrar esta {record_label}:\n"
        f"{data.get('title', 'Sin título')}\n"
        f"Ubicación: {location}\n"
        f"Tipo de ayuda: {tags}\n\n"
        "¿Está correcto? Responde sí para confirmar o no para corregir."
    )


def llm_close_summary(record: Offer | Demand) -> str:
    """Placeholder for LLM-generated close confirmation summary."""

    record_type = "oferta" if isinstance(record, Offer) else "solicitud"
    return (
        f"Encontré la {record_type} {record.public_id}: {record.title}\n"
        f"Ubicación: {record.address_text or record.administrative_area_name or 'sin ubicación'}\n\n"
        "¿Confirmas que quieres cerrarla? Responde sí para cerrar o no para cancelar."
    )


def handle_chatbot_message(session: Session, incoming: IncomingWhatsAppMessage) -> str:
    conversation = get_or_create_conversation(session, incoming)
    close_request = _parse_close_request(incoming.text)
    if close_request:
        reply = _start_close_confirmation(session, conversation, incoming, close_request)
    elif conversation.current_step == "confirm_close":
        reply = _handle_close_confirmation(session, conversation, incoming)
    elif conversation.current_step == "confirm_create":
        reply = _handle_create_confirmation(session, conversation, incoming)
    else:
        reply = _handle_collecting(session, conversation, incoming)
    record_bot_reply(session, conversation, text=reply)
    return reply


def _handle_collecting(session: Session, conversation: Conversation, incoming: IncomingWhatsAppMessage) -> str:
    interpreted = llm_interpret_user_message(conversation, incoming)
    intent = _intent_from_data(interpreted)
    merged_data = _merge_collected_data(conversation.collected_data, interpreted)
    merged_data["complete_fields"] = _complete_fields(merged_data)
    conversation = save_conversation_state(session, conversation, intent=intent, collected_data=merged_data)
    missing_fields = _missing_fields(conversation.collected_data)
    if missing_fields:
        save_conversation_state(session, conversation, current_step=f"ask_{missing_fields[0]}")
        return llm_next_question(missing_fields)

    reviewed = llm_review_completed_fields(conversation)
    conversation = save_conversation_state(session, conversation, collected_data={**conversation.collected_data, **reviewed})
    conversation = geocode_conversation_location(session, conversation)
    save_conversation_state(session, conversation, current_step="confirm_create")
    return llm_summary_message(conversation)


def _merge_collected_data(existing: dict[str, Any], new_data: dict[str, Any]) -> dict[str, Any]:
    merged = {**existing, **new_data}
    if not new_data.get("tags") and existing.get("tags"):
        merged["tags"] = existing["tags"]
    if not new_data.get("intent") and existing.get("intent"):
        merged["intent"] = existing["intent"]
    if not new_data.get("administrative_area_name") and existing.get("administrative_area_name"):
        merged["administrative_area_name"] = existing["administrative_area_name"]
    if not new_data.get("address_text") and existing.get("address_text"):
        merged["address_text"] = existing["address_text"]
    return merged


def _handle_create_confirmation(session: Session, conversation: Conversation, incoming: IncomingWhatsAppMessage) -> str:
    answer = incoming.text.strip().lower()
    if answer in NO_WORDS:
        save_conversation_state(session, conversation, current_step=None)
        return "Está bien. Dime qué quieres corregir."
    if answer not in YES_WORDS:
        return "Por favor responde sí para confirmar o no para corregir."

    data = conversation.collected_data
    create_kwargs = {
        "whatsapp_bsuid": incoming.from_bsuid,
        "whatsapp_name": incoming.contact_name,
        "phone_number": incoming.phone_number,
        "original_message": data["original_message"],
        "title": data["title"],
        "tags": data.get("tags", []),
        "administrative_area_name": data.get("administrative_area_name"),
        "administrative_area_level": data.get("administrative_area_level"),
        "address_text": data.get("address_text"),
        "geometry_geojson": data.get("geometry"),
    }
    if data["intent"] == "offer":
        record = create_offer(session, **create_kwargs)
        record_name = "oferta"
    else:
        record = create_demand(session, **create_kwargs)
        record_name = "solicitud"
    complete_conversation(session, conversation)
    return f"Listo, creé tu {record_name} con ID {record.public_id}. Para cerrarla después, escribe: cerrar {record.public_id}."


def _start_close_confirmation(
    session: Session,
    conversation: Conversation,
    incoming: IncomingWhatsAppMessage,
    close_request: tuple[RecordKind, str],
) -> str:
    record_kind, public_id = close_request
    record = _get_user_record_by_public_id(session, incoming.from_bsuid, record_kind, public_id)
    if record is None:
        return f"No encontré un registro abierto con ID {public_id.upper()} para este WhatsApp."
    save_conversation_state(
        session,
        conversation,
        current_step="confirm_close",
        collected_data={"close_record_type": record_kind, "close_public_id": public_id.upper()},
    )
    return llm_close_summary(record)


def _handle_close_confirmation(session: Session, conversation: Conversation, incoming: IncomingWhatsAppMessage) -> str:
    answer = incoming.text.strip().lower()
    if answer in NO_WORDS:
        save_conversation_state(session, conversation, current_step=None, collected_data={"close_public_id": None})
        return "No cerré el registro."
    if answer not in YES_WORDS:
        return "Por favor responde sí para cerrar el registro o no para cancelar."

    public_id = conversation.collected_data["close_public_id"]
    record_kind = conversation.collected_data["close_record_type"]
    if record_kind == "offer":
        close_offer_by_public_id(session, whatsapp_bsuid=incoming.from_bsuid, public_id=public_id)
        label = "oferta"
    else:
        close_demand_by_public_id(session, whatsapp_bsuid=incoming.from_bsuid, public_id=public_id)
        label = "solicitud"
    complete_conversation(session, conversation)
    return f"Listo, cerré la {label} {public_id}."


def _extract_placeholder_tags(lower_text: str) -> list[str]:
    known_tags = ["agua", "comida", "rescate", "transporte", "albergue", "maquinaria", "medicina", "ropa"]
    return [tag for tag in known_tags if tag in lower_text]


def _extract_placeholder_location(text: str) -> dict[str, str] | None:
    location_match = re.search(r"\b(?:en|desde|hacia)\s+(.+)$", text, flags=re.IGNORECASE)
    if not location_match:
        return None
    location = location_match.group(1).strip(" .")
    return {"administrative_area_name": location, "address_text": location}


def _complete_fields(data: dict[str, Any]) -> list[str]:
    complete = []
    for field in REQUIRED_FIELDS:
        if field == "location":
            if data.get("administrative_area_name") or data.get("address_text"):
                complete.append(field)
        elif data.get(field):
            complete.append(field)
    return complete


def _missing_fields(data: dict[str, Any]) -> list[str]:
    complete = set(_complete_fields(data))
    return [field for field in REQUIRED_FIELDS if field not in complete]


def _intent_from_data(data: dict[str, Any]) -> ConversationIntent | None:
    if data.get("intent") == "offer":
        return ConversationIntent.offer
    if data.get("intent") == "demand":
        return ConversationIntent.demand
    return None


def _parse_close_request(text: str) -> tuple[RecordKind, str] | None:
    match = re.search(r"\b(?:cerrar|close)\s+([do]\d+)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    public_id = match.group(1).upper()
    return ("offer" if public_id.startswith("O") else "demand", public_id)


def _get_user_record_by_public_id(
    session: Session,
    whatsapp_bsuid: str,
    record_kind: RecordKind,
    public_id: str,
) -> Offer | Demand | None:
    if record_kind == "offer":
        return session.exec(
            select(Offer)
            .join(OfferUser, Offer.id == OfferUser.offer_id)
            .join(User, User.id == OfferUser.user_id)
            .where(Offer.public_id == public_id.upper(), Offer.status == RecordStatus.open, User.whatsapp_bsuid == whatsapp_bsuid)
        ).first()
    return session.exec(
        select(Demand)
        .join(DemandUser, Demand.id == DemandUser.demand_id)
        .join(User, User.id == DemandUser.user_id)
        .where(Demand.public_id == public_id.upper(), Demand.status == RecordStatus.open, User.whatsapp_bsuid == whatsapp_bsuid)
    ).first()
