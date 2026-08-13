from fastapi.testclient import TestClient
from sqlmodel import Session, text

from help_matcher.database import engine, get_session
from help_matcher.main import app
from help_matcher.models import User


def clear_search_test_data() -> None:
    with Session(engine) as session:
        session.exec(text("""
            DELETE FROM offertag
            WHERE offer_id IN (SELECT offer.id FROM offer JOIN "user" ON "user".id = offer.user_id WHERE "user".name = 'Search user')
        """))
        session.exec(text("""
            DELETE FROM demandtag
            WHERE demand_id IN (SELECT demand.id FROM demand JOIN "user" ON "user".id = demand.user_id WHERE "user".name = 'Search user')
        """))
        session.exec(text('DELETE FROM offer USING "user" WHERE "user".id = offer.user_id AND "user".name = \'Search user\''))
        session.exec(text('DELETE FROM demand USING "user" WHERE "user".id = demand.user_id AND "user".name = \'Search user\''))
        session.exec(text('DELETE FROM "user" WHERE name = \'Search user\''))
        session.exec(text("""
            DELETE FROM tag
            WHERE name IN ('water', 'medicine')
            AND NOT EXISTS (SELECT 1 FROM offertag WHERE offertag.tag_id = tag.id)
            AND NOT EXISTS (SELECT 1 FROM demandtag WHERE demandtag.tag_id = tag.id)
        """))
        session.commit()


def test_search_records_across_types() -> None:
    clear_search_test_data()
    try:
        with Session(engine) as session:
            user = User(name="Search user")
            session.add(user)
            session.commit()
            session.refresh(user)

        client = TestClient(app)
        client.post(
            "/offers",
            json={
                "user_id": user.id,
                "original_message": "We can bring clean water",
                "administrative_area_name": "Chapinero",
                "address_text": "Main square",
                "tags": ["water"],
            },
        )
        client.post(
            "/demands",
            json={
                "user_id": user.id,
                "original_message": "Need medicine urgently",
                "administrative_area_name": "Laureles",
                "tags": ["medicine"],
            },
        )

        water = client.get("/search", params=[("q", "water"), ("record_type", "offer")])
        medicine = client.get("/search", params=[("q", "medicine"), ("record_type", "offer"), ("record_type", "demand")])

        assert water.status_code == 200
        water_results = [result for result in water.json() if result["record"]["original_message"] == "We can bring clean water"]
        assert [result["record_type"] for result in water_results] == ["offer"]
        assert medicine.status_code == 200
        medicine_results = [result for result in medicine.json() if result["record"]["original_message"] == "Need medicine urgently"]
        assert [result["record_type"] for result in medicine_results] == ["demand"]
    finally:
        app.dependency_overrides.pop(get_session, None)
        clear_search_test_data()
