import pytest

from mts_backend.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://unit:unit-secret@127.0.0.1:1/unit_test",
        api_docs_enabled=False,
    )
