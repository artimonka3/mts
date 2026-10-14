# ruff: noqa: B008 - FastAPI dependency defaults.
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import owned
from mts_backend.db.models import Agreement, DeliveryAttempt, OutboxEvent
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["deliveries"])


@router.get("/agreements/{agreement_id}/deliveries")
async def listing(
    agreement_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db=Depends(get_db),
):
    await owned(db, Agreement, agreement_id, user)
    rows = list(
        await db.scalars(
            select(OutboxEvent)
            .where(
                OutboxEvent.agreement_id == agreement_id,
            )
            .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
        )
    )
    items = []
    for row in rows[offset : offset + limit]:
        attempts = list(
            await db.scalars(
                select(DeliveryAttempt)
                .where(
                    DeliveryAttempt.event_id == row.id,
                )
                .order_by(DeliveryAttempt.attempt)
            )
        )
        items.append(
            {
                "id": row.id,
                "version": row.aggregate_version,
                "event_type": row.event_type,
                "status": row.status,
                "attempt": row.attempt,
                "attempts": [
                    {"attempt": x.attempt, "result": x.result, "response_code": x.response_code}
                    for x in attempts
                ],
            }
        )
    return {"items": items, "total": len(rows), "limit": limit, "offset": offset}
