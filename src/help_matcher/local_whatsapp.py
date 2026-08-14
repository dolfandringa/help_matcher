from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from help_matcher.config import Settings, get_settings
from help_matcher.whatsapp import extract_text_messages

router = APIRouter(prefix="/local/whatsapp", tags=["local-whatsapp"])


class LocalWhatsAppConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, whatsapp_bsuid: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(whatsapp_bsuid, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, whatsapp_bsuid: str) -> None:
        connections = self.active_connections.get(whatsapp_bsuid)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(whatsapp_bsuid, None)

    async def broadcast(self, whatsapp_bsuid: str, message: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        connections = self.active_connections.get(whatsapp_bsuid, set())
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except RuntimeError:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket, whatsapp_bsuid)


class LocalWhatsAppTextPayload(BaseModel):
    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str
    type: str
    text: dict[str, Any]
    context: dict[str, Any] | None = None


manager = LocalWhatsAppConnectionManager()


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


@router.websocket("/ws/{whatsapp_bsuid}")
async def local_whatsapp_socket(websocket: WebSocket, whatsapp_bsuid: str) -> None:
    await manager.connect(websocket, whatsapp_bsuid)
    try:
        await websocket.send_json(
            {
                "direction": "system",
                "timestamp": utc_timestamp(),
                "text": "Connected to the local WhatsApp simulator.",
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, whatsapp_bsuid)


@router.post("/webhook")
async def receive_local_whatsapp_webhook(
    payload: dict[str, Any],
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    for message in extract_text_messages(payload):
        await manager.broadcast(
            message.from_bsuid,
            {
                "direction": "incoming",
                "timestamp": utc_timestamp(),
                "message_id": message.message_id,
                "from_bsuid": message.from_bsuid,
                "contact_name": message.contact_name,
                "phone_number": message.phone_number,
                "text": message.text,
                "raw": payload,
            }
        )
        await manager.broadcast(
            message.from_bsuid,
            {
                "direction": "outgoing",
                "timestamp": utc_timestamp(),
                "message_id": f"local-reply-{datetime.now(UTC).timestamp()}",
                "sender_name": settings.bot_name,
                "to": message.from_bsuid,
                "text": "Thank you",
                "raw": {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": message.from_bsuid,
                    "context": {"message_id": message.message_id},
                    "type": "text",
                    "text": {"preview_url": False, "body": "Thank you"},
                },
            }
        )
    return {"status": "received"}


@router.get("/webhook")
def local_whatsapp_webhook_status() -> dict[str, str]:
    return {"status": "ready"}


@router.post("/graph/{api_version}/{phone_number_id}/messages")
async def receive_local_whatsapp_reply(
    api_version: str,
    phone_number_id: str,
    payload: LocalWhatsAppTextPayload,
    settings: Settings = Depends(get_settings),
) -> dict[str, list[dict[str, str]]]:
    message_id = f"local-reply-{datetime.now(UTC).timestamp()}"
    await manager.broadcast(
        payload.to,
        {
            "direction": "outgoing",
            "timestamp": utc_timestamp(),
            "message_id": message_id,
            "sender_name": settings.bot_name,
            "api_version": api_version,
            "phone_number_id": phone_number_id,
            "to": payload.to,
            "text": payload.text.get("body", ""),
            "raw": payload.model_dump(),
        }
    )
    return {"messages": [{"id": message_id}]}
