# ruff: noqa: B008 - FastAPI dependency defaults.
"""Owner-scoped task selection and explicit deadline semantics for the MVP."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Query
from sqlalchemy import select

from mts_backend.core.business import BusinessError, utcnow
from mts_backend.db.models import Agreement, Call


def deadline(data):
    due = data.get("due") or {"kind": "unknown"}
    kind = due.get("kind")
    if kind == "date_only":
        # Date-only expires at the next local midnight, without inventing a due time.
        day = date.fromisoformat(due["date"]) + timedelta(days=1)
        return datetime.combine(day, time.min, ZoneInfo(due.get("timezone", "Europe/Minsk")))
    if kind == "instant":
        return datetime.fromisoformat(due["at"].replace("Z", "+00:00"))
    if kind == "interval":
        return datetime.fromisoformat(due["end"].replace("Z", "+00:00"))
    return None


def overdue(agreement, now=None):
    end = deadline(agreement.data)
    return bool(
        agreement.verification == "accepted"
        and agreement.execution in {"open", "in_progress"}
        and end is not None
        and end <= (now or utcnow())
    )


def due_point(data):
    due = data.get("due") or {"kind": "unknown"}
    if due.get("kind") == "date_only":
        return datetime.combine(
            date.fromisoformat(due["date"]), time.min, ZoneInfo(due.get("timezone", "Europe/Minsk"))
        )
    if due.get("kind") == "interval":
        return datetime.fromisoformat(due["start"].replace("Z", "+00:00"))
    return deadline(data)


def date_bound(value, timezone_name="Europe/Minsk"):
    if value is None:
        return None
    try:
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), time.min, ZoneInfo(timezone_name))
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise BusinessError(
            422, "validation_error", "Date filter must include a valid offset."
        ) from None


class TaskFilters:
    def __init__(
        self,
        client_id: str | None = None,
        q: str | None = Query(default=None, max_length=200),
        execution: list[str] = Query(default=[]),
        priority: str | None = None,
        tag_id: list[str] = Query(default=[]),
        overdue: bool | None = None,
        needs_details: bool | None = None,
        due_from: str | None = None,
        due_to: str | None = None,
        accepted_from: str | None = None,
        accepted_to: str | None = None,
        is_demo: bool | None = None,
        sort: str = "due_asc",
        agreement_ids: list[str] = Query(default=[]),
    ):
        if any(x not in {"open", "in_progress", "done", "cancelled"} for x in execution):
            raise BusinessError(422, "validation_error", "Invalid execution filter.")
        if priority not in {None, "low", "normal", "high"}:
            raise BusinessError(422, "validation_error", "Invalid priority filter.")
        if sort not in {"due_asc", "created_desc", "priority_desc"}:
            raise BusinessError(422, "validation_error", "Invalid task sort.")
        try:
            for identity in [client_id, *tag_id, *agreement_ids]:
                if identity is not None:
                    UUID(identity)
        except (ValueError, TypeError):
            raise BusinessError(
                422, "validation_error", "Filter identifiers must be UUIDs."
            ) from None
        self.client_id = client_id
        self.q = q.casefold().strip() if isinstance(q, str) else None
        self.execution = execution
        self.priority = priority
        self.tags = set(tag_id)
        self.overdue = overdue
        self.needs_details = needs_details
        self.due_from = date_bound(due_from)
        self.due_to = date_bound(due_to)
        self.accepted_from = date_bound(accepted_from)
        self.accepted_to = date_bound(accepted_to)
        self.is_demo = is_demo
        self.sort = sort
        self.agreement_ids = set(agreement_ids)


async def select_tasks(db, user, filters):
    query = (
        select(Agreement, Call)
        .join(Call, Call.id == Agreement.call_id)
        .where(
            Agreement.owner_id == user.id,
            Agreement.organization_id == user.organization_id,
            Agreement.verification == "accepted",
            Agreement.deleted_at.is_(None),
            Call.deleted_at.is_(None),
        )
    )
    if filters.client_id:
        query = query.where(Call.client_id == filters.client_id)
    if filters.is_demo is not None:
        query = query.where(Call.is_demo == filters.is_demo)
    if filters.agreement_ids:
        query = query.where(Agreement.id.in_(filters.agreement_ids))
    rows = (await db.execute(query)).all()
    selected = []
    now = utcnow()
    for agreement, call in rows:
        data = agreement.data
        if (
            filters.q
            and filters.q not in data.get("action", "").casefold()
            and filters.q not in call.title.casefold()
        ):
            continue
        end = due_point(data)
        if filters.execution:
            if agreement.execution not in filters.execution:
                continue
        elif agreement.execution == "cancelled":
            continue
        if filters.priority and data.get("priority", "normal") != filters.priority:
            continue
        if not filters.tags.issubset(set(data.get("tag_ids", []))):
            continue
        if filters.overdue is not None and overdue(agreement, now) != filters.overdue:
            continue
        if (
            filters.needs_details is not None
            and bool(data.get("needs_details")) != filters.needs_details
        ):
            continue
        if filters.due_from and (end is None or end < filters.due_from):
            continue
        if filters.due_to and (end is None or end >= filters.due_to):
            continue
        accepted = agreement.accepted_at
        if filters.accepted_from and (accepted is None or accepted < filters.accepted_from):
            continue
        if filters.accepted_to and (accepted is None or accepted >= filters.accepted_to):
            continue
        selected.append(agreement)
    if filters.sort == "created_desc":
        selected.sort(key=lambda a: (a.created_at, a.id), reverse=True)
    elif filters.sort == "priority_desc":
        selected.sort(
            key=lambda a: (
                {"high": 0, "normal": 1, "low": 2}[a.data.get("priority", "normal")],
                a.id,
            )
        )
    else:
        infinity = datetime.max.replace(tzinfo=UTC)
        selected.sort(key=lambda a: (due_point(a.data) or infinity, a.id))
    return selected
