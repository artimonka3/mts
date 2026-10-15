"""Validated environment configuration. Never log a database URL."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MTS_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("postgresql+psycopg://mts:mts@localhost:5432/mts")
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    cors_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = False
    api_docs_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    session_cookie_name: str = "mts_session"
    session_ttl_seconds: int = Field(default=43200, ge=300, le=604800)
    session_cookie_secure: bool = False
    auth_login_max_attempts: int = Field(default=5, ge=1, le=100)
    auth_login_window_seconds: int = Field(default=300, ge=1, le=3600)
    audio_storage_path: str = "/tmp/mts-audio"
    data_encryption_key: SecretStr = SecretStr("")
    audio_encryption_key: SecretStr = SecretStr("")
    upload_max_bytes: int = Field(default=104857600, ge=1024, le=524288000)
    audio_max_seconds: int = Field(default=3600, ge=1, le=7200)
    decoder_timeout_seconds: int = Field(default=60, ge=1, le=300)
    audio_retention_days: int = Field(default=7, ge=1, le=3650)
    text_retention_days: int = Field(default=30, ge=1, le=3650)
    business_retention_days: int = Field(default=365, ge=1, le=3650)
    fixture_path: str = "../fixtures/dialogues_v1.json"
    job_lease_seconds: int = Field(default=120, ge=10, le=3600)
    crm_webhook_url: str = "http://mock-crm:8001/webhook"
    crm_webhook_token: SecretStr = SecretStr("")
    crm_max_attempts: int = Field(default=3, ge=1, le=10)
    worker_poll_seconds: float = Field(default=10, ge=0.1, le=3600)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            parsed = make_url(value.get_secret_value())
            if parsed.drivername != "postgresql+psycopg" or not parsed.database:
                raise ValueError("Database must use postgresql+psycopg and name a database.")
        except (ArgumentError, ValueError):
            raise ValueError("Invalid database connection configuration.") from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            try:
                parsed = urlsplit(origin)
                valid = (
                    parsed.scheme in {"http", "https"}
                    and parsed.hostname
                    and "*" not in origin
                    and not parsed.username
                    and not parsed.password
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and parsed.port != 0
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths.")
        return list(dict.fromkeys(origins))

    @model_validator(mode="after")
    def validate_production_docs(self) -> "Settings":
        if self.environment == "production" and self.api_docs_enabled:
            raise ValueError("API documentation must be disabled in production.")
        if self.environment == "production" and not self.session_cookie_secure:
            raise ValueError("Secure session cookies are required in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
