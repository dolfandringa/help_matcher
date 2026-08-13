from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from help_matcher.config import Settings
from help_matcher.models import Demand, Offer, RecordStatus, User
from help_matcher.whatsapp import (
    IncomingWhatsAppMessage,
    close_demand,
    close_offer,
    create_demand,
    create_offer,
    extract_text_messages,
    reply_to_message,
)


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_offer_creates_unknown_whatsapp_user() -> None:
    with make_session() as session:
        offer = create_offer(
            session,
            whatsapp_bsuid="bsuid-1",
            whatsapp_name="Ana",
            phone_number="+573001112233",
            original_message="Tengo agua para donar en Chapinero.",
            tags=["water"],
            administrative_area_name="Chapinero",
            administrative_area_level="locality",
        )

        user = session.get(User, offer.user_id)

        assert user is not None
        assert user.whatsapp_bsuid == "bsuid-1"
        assert [tag.name for tag in offer.tags] == ["water"]
        assert offer.administrative_area_name == "Chapinero"


def test_create_and_close_demand() -> None:
    with make_session() as session:
        demand = create_demand(
            session,
            whatsapp_bsuid="bsuid-2",
            original_message="Necesitamos carpas.",
            tags=["shelter"],
            address_text="Parque principal",
        )

        closed = close_demand(session, whatsapp_bsuid="bsuid-2", demand_id=demand.id)

        assert closed.status == RecordStatus.closed
        assert closed.closed_at is not None
        assert session.get(Demand, demand.id).status == RecordStatus.closed


def test_create_and_close_offer() -> None:
    with make_session() as session:
        offer = create_offer(
            session,
            whatsapp_bsuid="bsuid-3",
            original_message="Puedo transportar medicinas.",
            tags=["transport", "medicine"],
        )

        closed = close_offer(session, whatsapp_bsuid="bsuid-3", offer_id=offer.id)

        assert closed.status == RecordStatus.closed
        assert session.get(Offer, offer.id).status == RecordStatus.closed


def test_extract_text_messages_from_webhook_payload() -> None:
    messages = extract_text_messages(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"wa_id": "CO.123", "profile": {"name": "Ana"}},
                                ],
                                "messages": [
                                    {"id": "wamid.1", "from": "CO.123", "type": "text", "text": {"body": "Hola"}},
                                    {"id": "wamid.2", "from": "CO.123", "type": "image"},
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )

    assert messages == [
        IncomingWhatsAppMessage(
            message_id="wamid.1",
            from_bsuid="CO.123",
            text="Hola",
            contact_name="Ana",
            phone_number="CO.123",
        )
    ]


def test_reply_to_message_posts_contextual_whatsapp_reply(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"messages": [{"id": "reply-id"}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("help_matcher.whatsapp.httpx.post", fake_post)

    result = reply_to_message(
        IncomingWhatsAppMessage(message_id="wamid.1", from_bsuid="CO.123", text="Hola"),
        "Gracias, recibimos tu mensaje.",
        settings=Settings(
            _env_file=None,
            META_ACCESS_TOKEN="token",
            META_PHONE_NUMBER_ID="phone-number-id",
            META_API_VERSION="v20.0",
        ),
    )

    assert result == {"messages": [{"id": "reply-id"}]}
    assert captured["url"] == "https://graph.facebook.com/v20.0/phone-number-id/messages"
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["json"]["to"] == "CO.123"
    assert captured["json"]["context"] == {"message_id": "wamid.1"}
    assert captured["json"]["text"]["body"] == "Gracias, recibimos tu mensaje."
