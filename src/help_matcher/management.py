import uvicorn
from pydantic import Field
from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict
from sqlmodel import Session, select

from help_matcher.auth import hash_password
from help_matcher.database import engine
from help_matcher.models import OAuthIdentity, OAuthProvider, User, UserRole, utc_now


class ServeSettings(BaseSettings):
    """Run the Help Matcher FastAPI server."""

    host: str = Field(default="0.0.0.0", description="Host interface to bind.")
    port: int = Field(default=8000, description="Port to bind.")
    reload: bool = Field(default=False, description="Reload the server when code changes.")
    log_level: str = Field(default="info", description="Uvicorn log level.")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SERVER_",
        cli_parse_args=True,
        cli_prog_name="serve",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_show_env_vars=True,
        extra="ignore",
    )

    def cli_cmd(self) -> None:
        uvicorn.run(
            "help_matcher.main:app",
            host=self.host,
            port=self.port,
            reload=self.reload,
            log_level=self.log_level,
        )


def serve() -> None:
    CliApp.run(ServeSettings)


class CreateAdminSettings(BaseSettings):
    """Create or update an admin user."""

    username: str = Field(description="Admin username.")
    password: str = Field(description="Admin password.")
    name: str | None = Field(default=None, description="Optional display name.")
    update_existing: bool = Field(default=False, description="Update password/name if the admin already exists.")

    model_config = SettingsConfigDict(
        env_file=".env",
        cli_parse_args=True,
        cli_prog_name="create_admin",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        extra="ignore",
    )

    def cli_cmd(self) -> None:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.username == self.username)).first()
            if user is not None and not self.update_existing:
                raise SystemExit(
                    f"Admin username '{self.username}' already exists. "
                    "Use --update-existing to update the password."
                )
            if user is None:
                user = User(username=self.username, role=UserRole.admin)
                action = "Created"
            else:
                action = "Updated"

            user.password_hash = hash_password(self.password)
            user.role = UserRole.admin
            if self.name is not None:
                user.name = self.name
            user.updated_at = utc_now()
            session.add(user)
            session.commit()
            session.refresh(user)
            identity = session.exec(
                select(OAuthIdentity).where(
                    OAuthIdentity.provider == OAuthProvider.local,
                    OAuthIdentity.subject == self.username,
                )
            ).first()
            if identity is None:
                session.add(OAuthIdentity(user_id=user.id, provider=OAuthProvider.local, subject=self.username))
                session.commit()

        print(f"{action} admin user '{self.username}'.")


def create_admin() -> None:
    CliApp.run(CreateAdminSettings)
