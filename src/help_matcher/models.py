from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    admin = "admin"
    user = "user"


class RecordStatus(StrEnum):
    open = "open"
    closed = "closed"


class SearchRecordType(StrEnum):
    demand = "demand"
    offer = "offer"


class OAuthProvider(StrEnum):
    local = "local"
    google = "google"
    meta = "meta"


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


class OfferTag(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("offer_id", "tag_id"),)

    offer_id: int = Field(foreign_key="offer.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


class DemandTag(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("demand_id", "tag_id"),)

    demand_id: int = Field(foreign_key="demand.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


class TagBase(SQLModel):
    name: str = Field(min_length=1, max_length=100, index=True, unique=True)
    description: str | None = Field(default=None, max_length=500)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    offers: list["Offer"] = Relationship(back_populates="tags", link_model=OfferTag)
    demands: list["Demand"] = Relationship(back_populates="tags", link_model=DemandTag)


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int
    created_at: datetime
    updated_at: datetime


class HelpRecordBase(SQLModel):
    user_id: int = Field(foreign_key="user.id", index=True)
    original_message: str = Field(min_length=1)
    phone_number: str | None = Field(default=None, max_length=50, index=True)
    location_text: str | None = Field(default=None, max_length=500)
    administrative_area_name: str | None = Field(default=None, max_length=255, index=True)
    administrative_area_level: str | None = Field(default=None, max_length=100, index=True)
    address_text: str | None = Field(default=None, max_length=500)
    status: RecordStatus = Field(default=RecordStatus.open, index=True)


class Offer(HelpRecordBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tags: list[Tag] = Relationship(back_populates="offers", link_model=OfferTag)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None


class Demand(HelpRecordBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tags: list[Tag] = Relationship(back_populates="demands", link_model=DemandTag)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None


class HelpRecordCreate(HelpRecordBase):
    tags: list[str] = Field(default_factory=list)


class HelpRecordRead(HelpRecordBase):
    id: int
    tags: list[TagRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class OfferCreate(HelpRecordCreate):
    pass


class OfferRead(HelpRecordRead):
    pass


class DemandCreate(HelpRecordCreate):
    pass


class DemandRead(HelpRecordRead):
    pass


class SearchResult(SQLModel):
    record_type: SearchRecordType
    record: OfferRead | DemandRead
