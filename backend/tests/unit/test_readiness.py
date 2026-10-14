from unittest.mock import AsyncMock, MagicMock

import pytest

from mts_backend.db.readiness import check_readiness


def mocked_engine(revisions):
    engine = MagicMock()
    connection = AsyncMock()
    alive = MagicMock()
    alive.scalar_one.return_value = 1
    version_result = MagicMock()
    version_result.scalars.return_value.all.return_value = revisions
    connection.execute.side_effect = [alive, version_result]
    engine.connect.return_value.__aenter__.return_value = connection
    return engine, connection


async def test_readiness_checks_database_and_expected_schema():
    engine, connection = mocked_engine(["0003_encrypted_metadata"])
    assert await check_readiness(engine, 1) is True
    assert [str(call.args[0]) for call in connection.execute.await_args_list] == [
        "SELECT 1",
        "SELECT version_num FROM alembic_version",
    ]


@pytest.mark.parametrize(
    "revisions", [[], ["wrong_revision"], ["0003_encrypted_metadata", "another_head"]]
)
async def test_readiness_rejects_missing_wrong_or_multiple_revisions(revisions):
    engine, _ = mocked_engine(revisions)
    assert await check_readiness(engine, 1) is False


async def test_database_failure_is_not_raised_or_disclosed():
    engine, connection = mocked_engine([])
    connection.execute.side_effect = RuntimeError("database private-secret")
    assert await check_readiness(engine, 1) is False
