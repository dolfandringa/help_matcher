from sqlmodel import Session

from help_matcher.config import Settings
from help_matcher.models import Demand, Offer, RecordStatus, User
from help_matcher.whatsapp import (
    IncomingWhatsAppMessage,
    complete_conversation,
    close_demand,
    close_offer,
    create_demand,
    create_offer,
    extract_text_messages,
    geocode_conversation_location,
    get_or_create_conversation,
    record_bot_reply,
    reply_to_message,
    save_conversation_state,
)
from db import create_postgres_test_engine


def make_session() -> Session:
    engine = create_postgres_test_engine()
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

        user = offer.contacts[0]

        assert user is not None
        assert user.whatsapp_bsuid == "bsuid-1"
        assert [tag.name for tag in offer.tags] == ["water"]
        assert offer.administrative_area_name == "Chapinero"


def test_geocode_conversation_location_saves_geojson(monkeypatch) -> None:
    with make_session() as session:
        incoming = IncomingWhatsAppMessage(message_id="wamid.1", from_bsuid="CO.456", text="Necesito ayuda")
        conversation = get_or_create_conversation(session, incoming)
        conversation = save_conversation_state(
            session,
            conversation,
            collected_data={"administrative_area_name": "Cali", "address_text": "Calle 9 con 44"},
        )

        monkeypatch.setattr(
            "help_matcher.whatsapp.conversations.geocode_location",
            lambda **_: {"type": "Point", "coordinates": [-76.5402, 3.4225]},
        )

        conversation = geocode_conversation_location(session, conversation)
        demand = create_demand(
            session,
            whatsapp_bsuid="CO.456",
            original_message="Necesito ayuda",
            geometry_geojson=conversation.collected_data["geometry"],
        )

        assert conversation.collected_data["geometry"] == {"type": "Point", "coordinates": [-76.5402, 3.4225]}
        assert demand.geometry is not None


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

    monkeypatch.setattr("help_matcher.whatsapp.replies.httpx.post", fake_post)

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


def test_conversation_tracks_message_history_and_state() -> None:
    with make_session() as session:
        incoming = IncomingWhatsAppMessage(
            message_id="wamid.1",
            from_bsuid="CO.123",
            text="Necesito agua",
            contact_name="Ana",
            phone_number="CO.123",
        )

        conversation = get_or_create_conversation(session, incoming, current_step="classify_intent")
        conversation = save_conversation_state(
            session,
            conversation,
            current_step="ask_location",
            collected_data={"original_message": "Necesito agua", "tags": ["water"]},
            llm_context_summary="User needs water; location still missing.",
        )
        conversation = record_bot_reply(session, conversation, text="En que barrio estas?", meta_message_id="reply-1")
        conversation = complete_conversation(session, conversation)

        user = session.get(User, conversation.user_id)

        assert user is not None
        assert user.whatsapp_bsuid == "CO.123"
        assert conversation.status == "completed"
        assert conversation.current_step == "ask_location"
        assert conversation.collected_data["tags"] == ["water"]
        assert [message["role"] for message in conversation.message_history] == ["user", "assistant"]
        assert conversation.completed_at is not None
