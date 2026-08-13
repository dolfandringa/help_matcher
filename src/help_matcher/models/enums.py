from enum import StrEnum


class UserRole(StrEnum):
    admin = "admin"
    user = "user"


class RecordStatus(StrEnum):
    open = "open"
    closed = "closed"


class SearchRecordType(StrEnum):
    demand = "demand"
    offer = "offer"


class ConversationStatus(StrEnum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class ConversationIntent(StrEnum):
    unknown = "unknown"
    demand = "demand"
    offer = "offer"


class OAuthProvider(StrEnum):
    local = "local"
    google = "google"
    meta = "meta"

