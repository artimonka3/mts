# ruff: noqa: B008 - FastAPI dependency defaults.
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import owned, utcnow, version_check
from mts_backend.db.models import Notification
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def serialize(item):
    return {
        "id": item.id,
        "agreement_id": item.agreement_id,
        "kind": item.kind,
        "version": item.version,
        "created_at": item.created_at,
        "read_at": item.read_at,
    }


class MarkRead(BaseModel):
    expected_version: int = Field(ge=1)


@router.get("")
async def listing(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db=Depends(get_db),
):
    query = select(Notification).where(
        Notification.owner_id == user.id,
        Notification.organization_id == user.organization_id,
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows = list(
        await db.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc()))
    )
    return {
        "items": [serialize(x) for x in rows[offset : offset + limit]],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@router.post("/{notification_id}/read")
async def read(
    notification_id: str,
    body: MarkRead,
    user=Depends(current_user),
    db=Depends(get_db),
):
    item = await owned(db, Notification, notification_id, user)
    version_check(item, body.expected_version)
    if item.read_at is None:
        item.read_at = utcnow()
        item.version += 1
    return serialize(item)
