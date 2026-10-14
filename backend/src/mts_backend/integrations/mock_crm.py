# ruff: noqa: B008 - FastAPI dependency defaults.
"""Separate local CRM simulator. Persistent versioned state and tombstones."""

import hmac
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.core.business import utcnow
from mts_backend.core.config import get_settings
from mts_backend.db.models import MockCRMRecord
from mts_backend.db.readiness import build_engine


class CRMEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=36, max_length=36)
    agreement_id: str = Field(min_length=36, max_length=36)
    owner_id: str = Field(min_length=36, max_length=36)
    organization_id: str = Field(min_length=36, max_length=36)
    version: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=80)
    deleted: bool = False
    fields: dict = Field(default_factory=dict)
    execution: str | None = None

    @field_validator("event_id", "agreement_id", "owner_id", "organization_id")
    @classmethod
    def validate_id(cls, value):
        return str(UUID(value))


async def apply_event(db, event):
    from sqlalchemy import text

    # A per-aggregate PostgreSQL advisory transaction lock also protects the first insert.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:identity))"), {"identity": event.agreement_id}
    )
    row = await db.scalar(
        select(MockCRMRecord)
        .where(
            MockCRMRecord.agreement_id == event.agreement_id,
        )
        .with_for_update()
    )
    if row is not None:
        if row.owner_id != event.owner_id or row.organization_id != event.organization_id:
            raise HTTPException(409, "Aggregate owner differs.")
        if event.event_id in row.event_ids:
            return {"status": "duplicate", "version": row.version}
        if row.terminal:
            return {"status": "terminal_deleted", "version": row.version}
        if event.version <= row.version:
            return {"status": "stale", "version": row.version}
    else:
        row = MockCRMRecord(
            agreement_id=event.agreement_id,
            owner_id=event.owner_id,
            organization_id=event.organization_id,
            event_ids=[],
        )
        db.add(row)
    row.version = event.version
    row.deleted = event.deleted
    row.terminal = event.deleted and event.event_type == "deleted"
    row.payload = {} if event.deleted else event.model_dump(exclude={"event_id"})
    row.event_ids = (row.event_ids + [event.event_id])[-100:]
    row.updated_at = utcnow()
    await db.flush()
    return {"status": "applied", "version": row.version, "deleted": row.deleted}


def create_app(settings=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        engine = build_engine(settings)
        app.state.engine = engine
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Local mock CRM", lifespan=lifespan, docs_url=None, openapi_url=None)

    async def database():
        async with AsyncSession(app.state.engine, expire_on_commit=False) as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def authenticate(x_webhook_token: str = Header(default="")):
        expected = getattr(settings, "crm_webhook_token", "")
        if hasattr(expected, "get_secret_value"):
            expected = expected.get_secret_value()
        if not expected or not hmac.compare_digest(x_webhook_token, expected):
            raise HTTPException(401, "Webhook authentication required.")

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.post("/webhook", dependencies=[Depends(authenticate)])
    async def webhook(event: CRMEvent, db=Depends(database)):
        return await apply_event(db, event)

    return app


app = create_app()
