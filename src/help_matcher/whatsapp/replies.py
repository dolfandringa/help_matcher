from typing import Any

import httpx

from help_matcher.config import Settings, get_settings
from help_matcher.whatsapp.messages import IncomingWhatsAppMessage


def reply_to_message(
    incoming: IncomingWhatsAppMessage,
    text: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Reply to a specific incoming WhatsApp message."""

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

