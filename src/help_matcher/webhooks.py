import hmac
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlmodel import Session

from help_matcher.config import Settings, get_settings
from help_matcher.database import get_session
from help_matcher.whatsapp import extract_text_messages, handle_chatbot_message, reply_to_message

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])


def verify_meta_signature(body: bytes, signature_header: str | None, app_secret: str) -> None:
    if not app_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Meta app secret is not configured")
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Meta signature")

    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), body, sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Meta signature")


@router.get("/whatsapp", response_class=Response)
def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> Response:
    if hub_mode != "subscribe" or hub_verify_token != settings.meta_webhook_verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    body = await request.body()
    verify_meta_signature(body, x_hub_signature_256, settings.bot_client_secret)
    payload = await request.json()
    for incoming in extract_text_messages(payload):
        reply = handle_chatbot_message(session, incoming)
        reply_to_message(incoming, reply, settings=settings)
    return {"status": "processed"}
