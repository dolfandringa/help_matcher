from fastapi.testclient import TestClient
from sqlmodel import Session

from help_matcher.database import get_session
from help_matcher.main import app
from help_matcher.models import User
from db import create_postgres_test_engine


def make_engine():
    return create_postgres_test_engine()


def test_tag_endpoints_and_offer_tags() -> None:
    engine = make_engine()
    with Session(engine) as session:
        user = User(name="Tag user")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)

        created = client.post("/tags", json={"name": "Medical Supplies", "description": "Medicine and first aid"})
        offer = client.post(
            "/offers",
            json={
                "user_id": user_id,
                "title": "Botiquines disponibles",
                "original_message": "Tengo botiquines.",
                "tags": ["Medical Supplies", "medicine"],
            },
        )
        autocomplete = client.get("/tags/autocomplete", params={"q": "med"})
        tags = client.get("/tags")

        assert created.status_code == 201
        assert offer.status_code == 201
        assert [tag["name"] for tag in offer.json()["tags"]] == ["medical supplies", "medicine"]
        assert [tag["name"] for tag in autocomplete.json()] == ["medical supplies", "medicine"]
        assert [tag["name"] for tag in tags.json()] == ["medical supplies", "medicine"]
    finally:
        app.dependency_overrides.clear()
