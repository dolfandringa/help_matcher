"""Simple Python API for WhatsApp bot developers."""

from help_matcher.whatsapp.actions import close_demand, close_offer, create_demand, create_offer, get_or_create_user
from help_matcher.whatsapp.conversations import (
    abandon_conversation,
    complete_conversation,
    geocode_conversation_location,
    get_or_create_conversation,
    record_bot_reply,
    record_incoming_message,
    save_conversation_state,
)
from help_matcher.whatsapp.messages import IncomingWhatsAppMessage, extract_text_messages
from help_matcher.whatsapp.replies import reply_to_message

__all__ = [
    "IncomingWhatsAppMessage",
    "abandon_conversation",
    "close_demand",
    "close_offer",
    "complete_conversation",
    "create_demand",
    "create_offer",
    "extract_text_messages",
    "geocode_conversation_location",
    "get_or_create_conversation",
    "get_or_create_user",
    "record_bot_reply",
    "record_incoming_message",
    "reply_to_message",
    "save_conversation_state",
]
