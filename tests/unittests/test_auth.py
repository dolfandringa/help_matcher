from sqlmodel import Session

from help_matcher.auth import hash_password, login, login_form, oauth_login, record_oauth_identity, verify_password
from help_matcher.models import LoginRequest, OAuthIdentityCreate, OAuthLoginRequest, OAuthProvider, User, UserRole
from db import create_postgres_test_engine


def make_session() -> Session:
    engine = create_postgres_test_engine()
    return Session(engine)


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("very-secret-password")

    assert verify_password("very-secret-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_record_oauth_identity_and_login() -> None:
    with make_session() as session:
        user = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        session.add(user)
        session.commit()
        session.refresh(user)

        token = record_oauth_identity(
            OAuthIdentityCreate(
                user_id=user.id,
                provider=OAuthProvider.google,
                subject="google-user-123",
                email="admin@example.org",
            ),
            session,
        )
        oauth_token = oauth_login(
            OAuthLoginRequest(provider=OAuthProvider.google, subject="google-user-123"),
            session,
        )

        assert token.token_type == "bearer"
        assert oauth_token.user.id == user.id


def test_json_login() -> None:
    with make_session() as session:
        user = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        session.add(user)
        session.commit()
        session.refresh(user)

        token = login(LoginRequest(username="admin", password="password-123"), session)

        assert token.user.id == user.id


def test_form_login() -> None:
    with make_session() as session:
        user = User(username="admin", role=UserRole.admin, password_hash=hash_password("password-123"))
        session.add(user)
        session.commit()
        session.refresh(user)

        class FormData:
            username = "admin"
            password = "password-123"

        token = login_form(FormData(), session)

        assert token.user.id == user.id
