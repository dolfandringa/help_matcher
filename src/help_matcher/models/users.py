from datetime import datetime

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel

from help_matcher.models.enums import ConversationIntent, ConversationStatus, OAuthProvider, UserRole
from help_matcher.models.utils import utc_now


class UserBase(SQLModel):
    name: str | None = Field(default=None, max_length=200)
    username: str | None = Field(default=None, max_length=100, index=True, unique=True)
    phone_number: str | None = Field(default=None, max_length=50, index=True)
    whatsapp_bsuid: str | None = Field(default=None, max_length=200, index=True, unique=True)
    role: UserRole = Field(default=UserRole.user)
    oauth_provider: OAuthProvider | None = Field(default=None)
    oauth_subject: str | None = Field(default=None, max_length=255, index=True)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    whatsapp_bsuid: str = Field(max_length=200, index=True)
    status: ConversationStatus = Field(default=ConversationStatus.active, index=True)
    intent: ConversationIntent = Field(default=ConversationIntent.unknown, index=True)
    current_step: str | None = Field(default=None, max_length=100)
    last_message_id: str | None = Field(default=None, max_length=255)
    llm_context_summary: str | None = None
    collected_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    message_history: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8)


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime


class UserUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=200)
    username: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=50)
    whatsapp_bsuid: str | None = Field(default=None, max_length=200)
    role: UserRole | None = None
    oauth_provider: OAuthProvider | None = None
    oauth_subject: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8)


class OAuthIdentity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    provider: OAuthProvider = Field(index=True)
    subject: str = Field(max_length=255, index=True)
    email: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AdminCreate(SQLModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=200)


class LoginRequest(SQLModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class OAuthIdentityCreate(SQLModel):
    user_id: int
    provider: OAuthProvider
    subject: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class OAuthLoginRequest(SQLModel):
    provider: OAuthProvider
    subject: str = Field(min_length=1, max_length=255)


class TokenRead(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

