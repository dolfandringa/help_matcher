from dataclasses import dataclass, field
from uuid import uuid4

from pytest_bdd import given, parsers, scenarios, then, when
from sqlmodel import Session, select

from db import create_postgres_test_engine
from help_matcher.models import Demand, DemandUser, RecordStatus, User
from help_matcher.whatsapp import IncomingWhatsAppMessage
from help_matcher.whatsapp.chatbot import handle_chatbot_message


scenarios("features/chatbot_conversation.feature")


@dataclass
class ChatbotContext:
    session: Session
    whatsapp_bsuid: str = field(default_factory=lambda: f"e2e-chatbot-user-{uuid4().hex}")
    contact_name: str = "E2E Chatbot User"
    phone_number: str = "573001112233"
    message_counter: int = 0
    replies: list[str] = field(default_factory=list)


@given("a WhatsApp user is chatting with the bot", target_fixture="chatbot_context")
def whatsapp_user_chatting(monkeypatch) -> ChatbotContext:
    monkeypatch.setattr(
        "help_matcher.whatsapp.conversations.geocode_location",
        lambda **_: {"type": "Point", "coordinates": [-76.532, 3.4516]},
    )
    engine = create_postgres_test_engine()
    return ChatbotContext(session=Session(engine))


@when(parsers.parse('the user says "{message}"'))
def user_says(chatbot_context: ChatbotContext, message: str) -> None:
    chatbot_context.message_counter += 1
    incoming = IncomingWhatsAppMessage(
        message_id=f"e2e-message-{chatbot_context.message_counter}",
        from_bsuid=chatbot_context.whatsapp_bsuid,
        text=message,
        contact_name=chatbot_context.contact_name,
        phone_number=chatbot_context.phone_number,
    )
    chatbot_context.replies.append(handle_chatbot_message(chatbot_context.session, incoming))


@then("the bot asks the user to confirm a demand")
def bot_asks_to_confirm_demand(chatbot_context: ChatbotContext) -> None:
    reply = chatbot_context.replies[-1]
    assert "Voy a registrar esta solicitud de ayuda" in reply
    assert "¿Está correcto?" in reply


@then(parsers.parse('a demand is created with public id "{public_id}"'))
def demand_created(chatbot_context: ChatbotContext, public_id: str) -> None:
    demand = get_demand(chatbot_context, public_id)
    assert demand.public_id == public_id
    assert demand.status == RecordStatus.open
    assert demand.title == "Necesito agua y comida en Cali"
    assert {tag.name for tag in demand.tags} == {"agua", "comida"}


@then(parsers.parse('the bot tells the user how to close "{public_id}"'))
def bot_tells_user_how_to_close(chatbot_context: ChatbotContext, public_id: str) -> None:
    reply = chatbot_context.replies[-1]
    assert f"creé tu solicitud con ID {public_id}" in reply
    assert f"cerrar {public_id}" in reply


@then(parsers.parse('the bot asks the user to confirm closing "{public_id}"'))
def bot_asks_to_confirm_closing(chatbot_context: ChatbotContext, public_id: str) -> None:
    reply = chatbot_context.replies[-1]
    assert f"Encontré la solicitud {public_id}" in reply
    assert "¿Confirmas que quieres cerrarla?" in reply


@then(parsers.parse('demand "{public_id}" is closed'))
def demand_closed(chatbot_context: ChatbotContext, public_id: str) -> None:
    demand = get_demand(chatbot_context, public_id)
    assert demand.status == RecordStatus.closed
    assert chatbot_context.replies[-1] == f"Listo, cerré la solicitud {public_id}."
    chatbot_context.session.close()


def get_demand(chatbot_context: ChatbotContext, public_id: str) -> Demand:
    demand = chatbot_context.session.exec(
        select(Demand)
        .join(DemandUser, Demand.id == DemandUser.demand_id)
        .join(User, User.id == DemandUser.user_id)
        .where(Demand.public_id == public_id, User.whatsapp_bsuid == chatbot_context.whatsapp_bsuid)
    ).first()
    assert demand is not None
    return demand
