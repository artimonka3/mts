# ruff: noqa: B008 - FastAPI dependency defaults.
"""Dashboard with explicit accepted cohort and honest unmeasured savings."""

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import utcnow
from mts_backend.db.models import Agreement, Call
from mts_backend.db.session import get_db
from mts_backend.tasks.query import date_bound, overdue

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
    mode: Literal["real", "demo"] = "real",
    accepted_from: str | None = None,
    accepted_to: str | None = None,
    user=Depends(current_user),
    db=Depends(get_db),
):
    lower = date_bound(accepted_from)
    upper = date_bound(accepted_to)
    q = (
        select(Agreement)
        .join(Call, Agreement.call_id == Call.id)
        .where(
            Agreement.owner_id == user.id,
            Agreement.organization_id == user.organization_id,
            Agreement.deleted_at.is_(None),
            Call.deleted_at.is_(None),
            Call.is_demo == (mode == "demo"),
        )
    )
    rows = (await db.execute(q)).scalars().all()
    proposed = sum(a.verification == "proposed" for a in rows)
    cohort = [
        a
        for a in rows
        if a.verification == "accepted"
        and (not lower or a.accepted_at >= lower)
        and (not upper or a.accepted_at < upper)
    ]
    now = utcnow()
    completed = sum(a.execution == "done" for a in cohort)
    denominator = sum(a.execution != "cancelled" for a in cohort)
    return {
        "mode": mode,
        "as_of": now,
        "cohort": "accepted_at",
        "agreements_count": len(cohort),
        "proposed_count": proposed,
        "completed_count": completed,
        "cancelled_count": sum(a.execution == "cancelled" for a in cohort),
        "overdue_count": sum(overdue(a, now) for a in cohort),
        "completion_denominator": denominator,
        "completion_rate": completed / denominator if denominator else None,
        "saved_time": {"status": "not_measured", "seconds": None, "method": None},
        "model_accuracy": "not_measured",
    }
