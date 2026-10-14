"""Shared API and worker readiness check, including migration revision."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mts_backend.core.config import Settings
from mts_backend.core.logging import log_event

EXPECTED_SCHEMA_REVISION = "0003_encrypted_metadata"


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout_seconds},
    )


async def check_readiness(engine: AsyncEngine, timeout_seconds: int) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as connection:
                alive = await connection.execute(text("SELECT 1"))
                if alive.scalar_one() != 1:
                    return False
                revisions = await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                return set(revisions.scalars().all()) == {EXPECTED_SCHEMA_REVISION}
    except Exception:
        # Database diagnostics can include usernames, hosts, SQL parameters, and secrets.
        log_event("database_readiness_failed", level=logging.WARNING, ready=False)
        return False
