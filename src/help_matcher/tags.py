from sqlmodel import Session, select

from help_matcher.models import Demand, DemandTag, Offer, OfferTag, Tag


def normalize_tag_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def get_or_create_tag(session: Session, name: str) -> Tag:
    normalized = normalize_tag_name(name)
    tag = session.exec(select(Tag).where(Tag.name == normalized)).first()
    if tag is not None:
        return tag
    tag = Tag(name=normalized)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def link_tags(session: Session, record: Offer | Demand, tag_names: list[str]) -> None:
    seen: set[str] = set()
    for tag_name in tag_names:
        normalized = normalize_tag_name(tag_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tag = get_or_create_tag(session, normalized)
        if isinstance(record, Offer):
            session.add(OfferTag(offer_id=record.id, tag_id=tag.id))
        else:
            session.add(DemandTag(demand_id=record.id, tag_id=tag.id))
    session.commit()
    session.refresh(record)
