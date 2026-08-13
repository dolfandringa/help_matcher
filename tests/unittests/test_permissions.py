from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from help_matcher.auth import hash_password, token_for_user
from help_matcher.database import get_session
from help_matcher.main import app
from help_matcher.models import Offer, User, UserRole


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_create_user_requires_admin_token() -> None:
    engine = make_engine()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)

        response = client.post("/users", json={"name": "No auth"})

        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_create_user_allows_admin_token() -> None:
    engine = make_engine()
    with Session(engine) as session:
        admin = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        session.add(admin)
        session.commit()
        session.refresh(admin)
        token = token_for_user(admin).access_token

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)

        response = client.post(
            "/users",
            json={
                "name": "Created by admin",
                "username": "created-admin",
                "role": "admin",
                "password": "password-123",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Created by admin"
        assert "password" not in response.json()
        assert "password_hash" not in response.json()

        login_response = client.post(
            "/auth/login",
            json={"username": "created-admin", "password": "password-123"},
        )

        assert login_response.status_code == 200
        assert login_response.json()["user"]["username"] == "created-admin"
    finally:
        app.dependency_overrides.clear()


def test_list_users_requires_admin_token() -> None:
    engine = make_engine()
    with Session(engine) as session:
        admin = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        user = User(name="Regular user")
        session.add(admin)
        session.add(user)
        session.commit()
        session.refresh(admin)
        token = token_for_user(admin).access_token

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)

        unauthorized = client.get("/users")
        authorized = client.get("/users", headers={"Authorization": f"Bearer {token}"})

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
        assert len(authorized.json()) == 2
    finally:
        app.dependency_overrides.clear()


def test_close_offer_requires_admin_token() -> None:
    engine = make_engine()
    with Session(engine) as session:
        admin = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        user = User(name="Offer user")
        session.add(admin)
        session.add(user)
        session.commit()
        session.refresh(admin)
        session.refresh(user)
        offer = Offer(user_id=user.id, original_message="Can help")
        session.add(offer)
        session.commit()
        session.refresh(offer)
        token = token_for_user(admin).access_token

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)

        unauthorized = client.post(f"/offers/{offer.id}/close")
        authorized = client.post(f"/offers/{offer.id}/close", headers={"Authorization": f"Bearer {token}"})

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
        assert authorized.json()["status"] == "closed"
    finally:
        app.dependency_overrides.clear()
