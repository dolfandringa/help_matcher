from help_matcher.models import DemandCreate, OfferCreate


def test_help_records_accept_structured_location_fields() -> None:
    offer = OfferCreate(
        user_id=1,
        original_message="Tengo agua potable para entregar en Laureles.",
        administrative_area_name="Laureles",
        administrative_area_level="barrio",
        address_text="Parque de Laureles, Medellin",
    )
    demand = DemandCreate(
        user_id=1,
        original_message="Necesitamos carpas cerca al centro.",
        administrative_area_name="Medellin",
        administrative_area_level="municipality",
    )

    assert offer.address_text == "Parque de Laureles, Medellin"
    assert demand.administrative_area_name == "Medellin"

