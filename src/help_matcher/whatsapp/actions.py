from fastapi import HTTPException, status
from sqlmodel import Session, select

from help_matcher.models import Demand, DemandUser, Offer, OfferUser, RecordStatus, User, UserRole, utc_now
from help_matcher.tags import link_tags


def _title_from_message(message: str) -> str:
    return message.strip()[:200]


def get_or_create_user(
    session: Session,
    *,
    whatsapp_bsuid: str,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
) -> User:
    """Return the user linked to ``whatsapp_bsuid``, creating one if needed."""

    user = session.exec(select(User).where(User.whatsapp_bsuid == whatsapp_bsuid)).first()
    if user is not None:
        changed = False
        if whatsapp_name and not user.name:
            user.name = whatsapp_name
            changed = True
        if phone_number and not user.phone_number:
            user.phone_number = phone_number
            changed = True
        if changed:
            user.updated_at = utc_now()
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    user = User(
        whatsapp_bsuid=whatsapp_bsuid,
        name=whatsapp_name,
        phone_number=phone_number,
        role=UserRole.user,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_offer(
    session: Session,
    *,
    whatsapp_bsuid: str,
    original_message: str,
    title: str | None = None,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
    tags: list[str] | None = None,
    location_text: str | None = None,
    administrative_area_name: str | None = None,
    administrative_area_level: str | None = None,
    address_text: str | None = None,
) -> Offer:
    """Create an ``Offer`` from a WhatsApp conversation."""

    user = get_or_create_user(
        session,
        whatsapp_bsuid=whatsapp_bsuid,
        whatsapp_name=whatsapp_name,
        phone_number=phone_number,
    )
    offer = Offer(
        title=title or _title_from_message(original_message),
        original_message=original_message,
        location_text=location_text,
        administrative_area_name=administrative_area_name,
        administrative_area_level=administrative_area_level,
        address_text=address_text,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)
    session.add(OfferUser(offer_id=offer.id, user_id=user.id))
    session.commit()
    session.refresh(offer)
    link_tags(session, offer, tags or [])
    return offer


def create_demand(
    session: Session,
    *,
    whatsapp_bsuid: str,
    original_message: str,
    title: str | None = None,
    whatsapp_name: str | None = None,
    phone_number: str | None = None,
    tags: list[str] | None = None,
    location_text: str | None = None,
    administrative_area_name: str | None = None,
    administrative_area_level: str | None = None,
    address_text: str | None = None,
) -> Demand:
    """Create a ``Demand`` from a WhatsApp conversation."""

    user = get_or_create_user(
        session,
        whatsapp_bsuid=whatsapp_bsuid,
        whatsapp_name=whatsapp_name,
        phone_number=phone_number,
    )
    demand = Demand(
        title=title or _title_from_message(original_message),
        original_message=original_message,
        location_text=location_text,
        administrative_area_name=administrative_area_name,
        administrative_area_level=administrative_area_level,
        address_text=address_text,
    )
    session.add(demand)
    session.commit()
    session.refresh(demand)
    session.add(DemandUser(demand_id=demand.id, user_id=user.id))
    session.commit()
    session.refresh(demand)
    link_tags(session, demand, tags or [])
    return demand


def close_offer(session: Session, *, whatsapp_bsuid: str, offer_id: int) -> Offer:
    """Close an offer created by the WhatsApp user."""

    user = _get_user_or_404(session, whatsapp_bsuid)
    offer = session.get(Offer, offer_id)
    if offer is None or not any(contact.id == user.id for contact in offer.contacts):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    offer.status = RecordStatus.closed
    offer.closed_at = utc_now()
    offer.updated_at = utc_now()
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return offer


def close_demand(session: Session, *, whatsapp_bsuid: str, demand_id: int) -> Demand:
    """Close a demand created by the WhatsApp user."""

    user = _get_user_or_404(session, whatsapp_bsuid)
    demand = session.get(Demand, demand_id)
    if demand is None or not any(contact.id == user.id for contact in demand.contacts):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    demand.status = RecordStatus.closed
    demand.closed_at = utc_now()
    demand.updated_at = utc_now()
    session.add(demand)
    session.commit()
    session.refresh(demand)
    return demand


def _get_user_or_404(session: Session, whatsapp_bsuid: str) -> User:
    user = session.exec(select(User).where(User.whatsapp_bsuid == whatsapp_bsuid)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp user not found")
    return user
