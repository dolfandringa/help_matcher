from pydantic_settings import CliApp
from sqlmodel import Session

from help_matcher.auth import verify_password
from help_matcher.management import CreateAdminSettings, ServeSettings
from help_matcher.models import User, UserRole
from db import create_postgres_test_engine


def test_serve_settings_starts_uvicorn_with_defaults(monkeypatch) -> None:
    captured = {}

    def fake_run(app: str, **kwargs) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr("help_matcher.management.uvicorn.run", fake_run)

    CliApp.run(ServeSettings, cli_args=[])

    assert captured == {
        "app": "help_matcher.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,
        "log_level": "info",
    }


def test_create_admin_settings_creates_admin(monkeypatch, capsys) -> None:
    engine = create_postgres_test_engine()
    monkeypatch.setattr("help_matcher.management.engine", engine)

    CliApp.run(CreateAdminSettings, cli_args=["--username", "test", "--password", "test"])

    with Session(engine) as session:
        user = session.get(User, 1)

    assert user is not None
    assert user.username == "test"
    assert user.role == UserRole.admin
    assert user.password_hash is not None
    assert verify_password("test", user.password_hash)
    assert "Created admin user 'test'." in capsys.readouterr().out
