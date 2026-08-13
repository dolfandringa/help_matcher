from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from help_matcher.models.enums import RecordStatus, SearchRecordType
from help_matcher.models.utils import utc_now


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

