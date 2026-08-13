from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

from help_matcher.auth import hash_password, require_admin
from help_matcher.database import get_session
from help_matcher.models import (
    Demand,
    DemandCreate,
    DemandRead,
    OAuthIdentity,
    OAuthProvider,
    Offer,
    OfferCreate,
    OfferRead,
    RecordStatus,
    SearchRecordType,
    SearchResult,
    Tag,
    TagCreate,
    TagRead,
    User,
    UserCreate,
    UserRead,
    UserUpdate,
    utc_now,
)
from help_matcher.tags import get_or_create_tag, link_tags, normalize_tag_name

router = APIRouter()

TRecord = TypeVar("TRecord", Offer, Demand)

SEARCH_SQL = {
    SearchRecordType.offer: text("""
        WITH records AS (
            SELECT
                offer.id,
                to_tsvector(
                    'simple',
                    concat_ws(
                        ' ',
                        offer.original_message,
                        offer.administrative_area_name,
                        offer.administrative_area_level,
                        offer.address_text,
                        string_agg(tag.name, ' ')
                    )
                ) AS search_vector
            FROM offer
            LEFT JOIN offertag ON offertag.offer_id = offer.id
            LEFT JOIN tag ON tag.id = offertag.tag_id
            GROUP BY offer.id
        ),
        query AS (
            SELECT websearch_to_tsquery('simple', :q) AS value
        )
        SELECT records.id
        FROM records, query
        WHERE records.search_vector @@ query.value
        ORDER BY ts_rank(records.search_vector, query.value) DESC
        LIMIT :limit
    """),
    SearchRecordType.demand: text("""
        WITH records AS (
            SELECT
                demand.id,
                to_tsvector(
                    'simple',
                    concat_ws(
                        ' ',
                        demand.original_message,
                        demand.administrative_area_name,
                        demand.administrative_area_level,
                        demand.address_text,
                        string_agg(tag.name, ' ')
                    )
                ) AS search_vector
            FROM demand
            LEFT JOIN demandtag ON demandtag.demand_id = demand.id
            LEFT JOIN tag ON tag.id = demandtag.tag_id
            GROUP BY demand.id
        ),
        query AS (
            SELECT websearch_to_tsquery('simple', :q) AS value
        )
        SELECT records.id
        FROM records, query
        WHERE records.search_vector @@ query.value
        ORDER BY ts_rank(records.search_vector, query.value) DESC
        LIMIT :limit
    """),
}


def get_user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def close_record(session: Session, model: type[TRecord], record_id: int) -> TRecord:
    record = session.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found")
    record.status = RecordStatus.closed
    record.closed_at = utc_now()
    record.updated_at = utc_now()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_record(session: Session, model: type[TRecord], payload: SQLModel) -> TRecord:
    get_user_or_404(session, payload.user_id)  # type: ignore[attr-defined]
    record = model.model_validate(payload.model_dump(exclude={"tags"}))
    session.add(record)
    session.commit()
    session.refresh(record)
    link_tags(session, record, getattr(payload, "tags", []))
    return record


@router.get("/search", response_model=list[SearchResult])
def search_records(
    q: str = Query(min_length=1),
    record_type: list[SearchRecordType] = Query(default=[SearchRecordType.demand, SearchRecordType.offer]),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for current_type in dict.fromkeys(record_type):
        rows = session.exec(SEARCH_SQL[current_type], params={"q": q, "limit": limit}).all()
        model = Offer if current_type == SearchRecordType.offer else Demand
        for record_id in rows:
            record = session.get(model, record_id)
            if record is not None:
                results.append(SearchResult(record_type=current_type, record=record))
    return results[:limit]


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, session: Session = Depends(get_session)) -> Tag:
    tag = get_or_create_tag(session, payload.name)
    if payload.description is not None:
        tag.description = payload.description
        tag.updated_at = utc_now()
        session.add(tag)
        session.commit()
        session.refresh(tag)
    return tag


@router.get("/tags", response_model=list[TagRead])
def list_tags(session: Session = Depends(get_session)) -> list[Tag]:
    return list(session.exec(select(Tag).order_by(Tag.name)).all())


@router.get("/tags/autocomplete", response_model=list[TagRead])
def autocomplete_tags(
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> list[Tag]:
    query = normalize_tag_name(q)
    starts_with = list(
        session.exec(select(Tag).where(Tag.name.ilike(f"{query}%")).order_by(Tag.name).limit(limit)).all()
    )
    if len(starts_with) >= limit:
        return starts_with
    seen_ids = {tag.id for tag in starts_with}
    contains = list(
        session.exec(select(Tag).where(Tag.name.ilike(f"%{query}%")).order_by(Tag.name).limit(limit)).all()
    )
    return starts_with + [tag for tag in contains if tag.id not in seen_ids][: limit - len(starts_with)]


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> User:
    user_data = payload.model_dump(exclude={"password"})
    user = User.model_validate(user_data)
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    if payload.password is not None and user.username is not None:
        session.add(OAuthIdentity(user_id=user.id, provider=OAuthProvider.local, subject=user.username))
        session.commit()
        session.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead], dependencies=[Depends(require_admin)])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    return list(session.exec(select(User)).all())


@router.get("/users/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
def read_user(user_id: int, session: Session = Depends(get_session)) -> User:
    return get_user_or_404(session, user_id)


@router.patch("/users/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
def update_user(user_id: int, payload: UserUpdate, session: Session = Depends(get_session)) -> User:
    user = get_user_or_404(session, user_id)
    updates = payload.model_dump(exclude_unset=True, exclude={"password"})
    for key, value in updates.items():
        setattr(user, key, value)
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    if payload.password is not None and user.username is not None:
        identity = session.exec(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == OAuthProvider.local,
                OAuthIdentity.subject == user.username,
            )
        ).first()
        if identity is None:
            session.add(OAuthIdentity(user_id=user.id, provider=OAuthProvider.local, subject=user.username))
            session.commit()
            session.refresh(user)
    return user


@router.post("/offers", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
def create_offer(payload: OfferCreate, session: Session = Depends(get_session)) -> Offer:
    return create_record(session, Offer, payload)


@router.get("/offers", response_model=list[OfferRead])
def list_offers(
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    tag: str | None = None,
    session: Session = Depends(get_session),
) -> list[Offer]:
    statement = select(Offer)
    if status_filter is not None:
        statement = statement.where(Offer.status == status_filter)
    records = list(session.exec(statement).all())
    if tag is not None:
        normalized = normalize_tag_name(tag)
        records = [record for record in records if any(record_tag.name == normalized for record_tag in record.tags)]
    return records


@router.get("/offers/{offer_id}", response_model=OfferRead)
def read_offer(offer_id: int, session: Session = Depends(get_session)) -> Offer:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


@router.post("/offers/{offer_id}/close", response_model=OfferRead, dependencies=[Depends(require_admin)])
def close_offer(offer_id: int, session: Session = Depends(get_session)) -> Offer:
    return close_record(session, Offer, offer_id)


@router.post("/demands", response_model=DemandRead, status_code=status.HTTP_201_CREATED)
def create_demand(payload: DemandCreate, session: Session = Depends(get_session)) -> Demand:
    return create_record(session, Demand, payload)


@router.get("/demands", response_model=list[DemandRead])
def list_demands(
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    tag: str | None = None,
    session: Session = Depends(get_session),
) -> list[Demand]:
    statement = select(Demand)
    if status_filter is not None:
        statement = statement.where(Demand.status == status_filter)
    records = list(session.exec(statement).all())
    if tag is not None:
        normalized = normalize_tag_name(tag)
        records = [record for record in records if any(record_tag.name == normalized for record_tag in record.tags)]
    return records


@router.get("/demands/{demand_id}", response_model=DemandRead)
def read_demand(demand_id: int, session: Session = Depends(get_session)) -> Demand:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    return demand


@router.post("/demands/{demand_id}/close", response_model=DemandRead, dependencies=[Depends(require_admin)])
def close_demand(demand_id: int, session: Session = Depends(get_session)) -> Demand:
    return close_record(session, Demand, demand_id)
