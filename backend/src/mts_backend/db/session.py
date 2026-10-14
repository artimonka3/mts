"""One request transaction, shared by cached FastAPI dependencies."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.db.encryption import encryption_cipher


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    encryption_cipher()  # Explicit 503 before statement wrapping if the process key is missing.
    async with AsyncSession(request.app.state.engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
