from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IncomingWhatsAppMessage:
    """A normalized text message extracted from a Meta WhatsApp webhook payload."""

    message_id: str
    from_bsuid: str
    text: str
    contact_name: str | None = None
    phone_number: str | None = None


def extract_text_messages(payload: dict[str, Any]) -> list[IncomingWhatsAppMessage]:
    """Extract text messages from a Meta WhatsApp webhook payload."""

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

