# ruff: noqa: B008 - FastAPI dependency defaults.
import hashlib
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, uid, version_check
from mts_backend.db.models import Agreement, IdempotencyRecord
from mts_backend.db.session import get_db
from mts_backend.exports.routes import router as exports_router
from mts_backend.integrations.routes import router as delivery_router
from mts_backend.notifications.routes import router as notifications_router
from mts_backend.settings.routes import router as settings_router
from mts_backend.tasks.effects import agreement_changed
from mts_backend.tasks.query import TaskFilters, date_bound, due_point, select_tasks

router = APIRouter(prefix="/api/v1", tags=["tasks"])


class ExecutionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    action: Literal["start", "complete", "cancel", "reopen"]


TRANSITIONS = {
    ("open", "start"): "in_progress",
    ("open", "complete"): "done",
    ("in_progress", "complete"): "done",
    ("open", "cancel"): "cancelled",
    ("in_progress", "cancel"): "cancelled",
    ("done", "reopen"): "open",
    ("cancelled", "reopen"): "open",
}


@router.post("/agreements/{agreement_id}/execution")
async def execute(
    agreement_id: str,
    body: ExecutionAction,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user=Depends(current_user),
    db=Depends(get_db),
):
    from mts_backend.agreements.service import save_revision, serialize_agreement

    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", idempotency_key):
        raise BusinessError(422, "validation_error", "Invalid idempotency key.")
    item = await owned(db, Agreement, agreement_id, user)
    operation = "execution:" + agreement_id
    digest = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    previous = await db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.owner_id == user.id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if previous:
        if previous.digest != digest:
            raise BusinessError(409, "idempotency_conflict", "Key already used with another body.")
        return previous.response
    version_check(item, body.expected_version)
    target = TRANSITIONS.get((item.execution, body.action))
    if item.verification != "accepted" or target is None:
        raise BusinessError(409, "invalid_transition", "Execution transition is not allowed.")
    item.execution = target
    item.version += 1
    await save_revision(db, item)
    await agreement_changed(db, item, "agreement.execution")
    await audit(db, user, item, "execution_" + body.action, ["execution"])
    response = await serialize_agreement(db, item)
    db.add(
        IdempotencyRecord(
            id=uid(),
            owner_id=user.id,
            operation=operation,
            key=idempotency_key,
            digest=digest,
            response=response,
            status_code=200,
        )
    )
    return response


@router.get("/tasks")
async def listing(
    filters: TaskFilters = Depends(),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db=Depends(get_db),
):
    from mts_backend.agreements.service import serialize_agreement

    rows = await select_tasks(db, user, filters)
    return {
        "items": [await serialize_agreement(db, x) for x in rows[offset : offset + limit]],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/tasks/calendar")
async def calendar(
    from_: str = Query(alias="from"),
    to: str = Query(),
    filters: TaskFilters = Depends(),
    user=Depends(current_user),
    db=Depends(get_db),
):
    from mts_backend.agreements.service import serialize_agreement

    start, end = date_bound(from_), date_bound(to)
    if start >= end:
        raise BusinessError(422, "validation_error", "Calendar range must be increasing.")
    rows = await select_tasks(db, user, filters)
    skipped = [x.id for x in rows if due_point(x.data) is None]
    selected = [
        x for x in rows if due_point(x.data) is not None and start <= due_point(x.data) < end
    ]
    return {
        "items": [await serialize_agreement(db, x) for x in selected],
        "skipped_ids": skipped,
        "from": from_,
        "to": to,
    }


# Own routers already carry their complete API prefixes.
aggregate_router = APIRouter()
aggregate_router.include_router(router)
aggregate_router.include_router(settings_router)
aggregate_router.include_router(exports_router)
aggregate_router.include_router(notifications_router)
aggregate_router.include_router(delivery_router)
router = aggregate_router
