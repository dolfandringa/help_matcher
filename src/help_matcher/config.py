from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", validation_alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="help_matcher", validation_alias="POSTGRES_DB")
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")
    bot_client_id: str = Field(default="", validation_alias="BOT_CLIENT_ID")
    bot_client_secret: str = Field(default="", validation_alias="BOT_CLIENT_SECRET")
    meta_webhook_verify_token: str = Field(default="", validation_alias="META_WEBHOOK_VERIFY_TOKEN")
    meta_access_token: str = Field(default="", validation_alias="META_ACCESS_TOKEN")
    meta_phone_number_id: str = Field(default="", validation_alias="META_PHONE_NUMBER_ID")
    meta_api_version: str = Field(default="v20.0", validation_alias="META_API_VERSION")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    jwt_secret_key: str = Field(
        default="change-me-in-production-at-least-32-chars",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, validation_alias="JWT_EXPIRE_MINUTES")
    nominatim_base_url: str = Field(default="https://nominatim.openstreetmap.org", validation_alias="NOMINATIM_BASE_URL")
    nominatim_user_agent: str = Field(default="help-matcher/0.1", validation_alias="NOMINATIM_USER_AGENT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
