from typing import Any

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when
from sqlmodel import Session, select, text

from help_matcher.database import engine
from help_matcher.main import app
from help_matcher.models import Tag, User


scenarios("features/search_records.feature")


def clear_e2e_data() -> None:
    with Session(engine) as session:
        session.exec(text("""
            DELETE FROM offertag
            WHERE offer_id IN (
                SELECT offer.id FROM offer
                JOIN "user" ON "user".id = offer.user_id
                WHERE "user".name = 'E2E Search User'
            )
        """))
        session.exec(text("""
            DELETE FROM demandtag
            WHERE demand_id IN (
                SELECT demand.id FROM demand
                JOIN "user" ON "user".id = demand.user_id
                WHERE "user".name = 'E2E Search User'
            )
        """))
        session.exec(text("""DELETE FROM offer USING "user" WHERE "user".id = offer.user_id AND "user".name = 'E2E Search User'"""))
        session.exec(text("""DELETE FROM demand USING "user" WHERE "user".id = demand.user_id AND "user".name = 'E2E Search User'"""))
        session.exec(text("""DELETE FROM "user" WHERE name = 'E2E Search User'"""))
        session.commit()

        for tag in session.exec(select(Tag).where(Tag.name.in_(["water", "filters", "medicine", "shelter"]))).all():
            if not tag.offers and not tag.demands:
                session.delete(tag)
        session.commit()


@given("the database has multiple offers and demands with administrative locations and addresses")
def multiple_offers_and_demands() -> None:
    clear_e2e_data()
    client = TestClient(app)
    with Session(engine) as session:
        user = User(name="E2E Search User")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    client.post(
        "/offers",
        json={
            "user_id": user_id,
            "title": "Clean water available",
            "original_message": "Clean water available",
            "administrative_area_name": "Chapinero",
            "administrative_area_level": "locality",
            "address_text": "Community Center, Calle 10",
            "tags": ["water"],
        },
    )
    client.post(
        "/offers",
        json={
            "user_id": user_id,
            "title": "Blankets available",
            "original_message": "Blankets available",
            "administrative_area_name": "Laureles",
            "administrative_area_level": "barrio",
            "address_text": "North shelter",
            "tags": ["shelter"],
        },
    )
    client.post(
        "/demands",
        json={
            "user_id": user_id,
            "title": "Need water filters",
            "original_message": "Need water filters",
            "administrative_area_name": "Chapinero",
            "administrative_area_level": "locality",
            "address_text": "School gym, Carrera 7",
            "tags": ["filters", "water"],
        },
    )
    client.post(
        "/demands",
        json={
            "user_id": user_id,
            "title": "Need medical supplies",
            "original_message": "Need medical supplies",
            "administrative_area_name": "Centro",
            "administrative_area_level": "municipality",
            "address_text": "Main hospital",
            "tags": ["medicine"],
        },
    )


@when('I search for "water" in offers and demands', target_fixture="search_results")
def search_water() -> list[dict[str, Any]]:
    return run_search("water")


@when('I search for "Chapinero" in offers and demands', target_fixture="search_results")
def search_chapinero() -> list[dict[str, Any]]:
    return run_search("Chapinero")


@when('I search for "Community Center" in offers and demands', target_fixture="search_results")
def search_community_center() -> list[dict[str, Any]]:
    return run_search("Community Center")


def run_search(query: str) -> list[dict[str, Any]]:
    client = TestClient(app)
    response = client.get("/search", params=[("q", query), ("record_type", "offer"), ("record_type", "demand")])
    assert response.status_code == 200
    return response.json()


@then('the search results include an offer for "Clean water available"')
def search_includes_offer(search_results: list[dict[str, Any]]) -> None:
    assert any(
        result["record_type"] == "offer" and result["record"]["original_message"] == "Clean water available"
        for result in search_results
    )


@then('the search results include a demand for "Need water filters"')
def search_includes_demand(search_results: list[dict[str, Any]]) -> None:
    assert any(
        result["record_type"] == "demand" and result["record"]["original_message"] == "Need water filters"
        for result in search_results
    )


@then('the search results do not include "Need medical supplies"')
def search_excludes_unmatched_demand(search_results: list[dict[str, Any]]) -> None:
    assert all(result["record"]["original_message"] != "Need medical supplies" for result in search_results)
