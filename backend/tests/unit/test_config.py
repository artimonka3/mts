import pytest
from pydantic import ValidationError

from mts_backend.core.config import Settings


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///local.db",
        "postgresql+asyncpg://unit:private-password@localhost/unit",
        "not-a-url-private-password",
        "postgresql+psycopg://unit:private-password@localhost",
    ],
)
def test_invalid_database_config_is_rejected_without_input(database_url):
    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None, database_url=database_url)
    assert "private-password" not in str(raised.value)


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "https://example.com/path",
        "https://user:password@example.com",
        "https://example.com?token=secret",
        "file:///private",
        "https://example.com:invalid",
    ],
)
def test_invalid_cors_origin_is_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin], cors_allow_credentials=True)


def test_production_requires_docs_disabled():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", api_docs_enabled=True)
    assert Settings(
        _env_file=None, environment="production", api_docs_enabled=False, session_cookie_secure=True
    )


def test_env_database_url_is_secret(monkeypatch):
    monkeypatch.setenv(
        "MTS_DATABASE_URL", "postgresql+psycopg://unit:private-secret@localhost/unit"
    )
    monkeypatch.setenv("MTS_WORKER_POLL_SECONDS", "1.5")
    settings = Settings(_env_file=None)
    assert "private-secret" not in repr(settings)
    assert "private-secret" in settings.database_url.get_secret_value()
    assert settings.worker_poll_seconds == 1.5


@pytest.mark.parametrize("value", [0, 31])
def test_database_timeout_is_bounded(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_connect_timeout_seconds=value)
