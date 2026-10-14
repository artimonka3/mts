"""Atomic reminders and CRM outbox effects inside an agreement transaction."""

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from mts_backend.core.business import uid, utcnow
from mts_backend.db.models import OutboxEvent, Reminder, Setting
from mts_backend.tasks.query import deadline


async def agreement_changed(db, agreement, event_type):
    now = utcnow()
    await db.execute(
        update(Reminder)
        .where(Reminder.agreement_id == agreement.id, Reminder.status == "scheduled")
        .values(status="cancelled")
    )
    data = agreement.data
    accepted = agreement.verification == "accepted" and agreement.deleted_at is None
    deliverable = (
        accepted
        and deadline(data) is not None
        and not data.get("due", {}).get("ambiguous", False)
        and (not data.get("condition") or bool(data.get("condition_resolution")))
        and not data.get("needs_details")
        and bool(data.get("obligor_participant_id"))
        and bool(data.get("recipient_participant_id"))
    )
    if deliverable and agreement.execution in {"open", "in_progress"}:
        policy = await db.scalar(
            select(Setting).where(
                Setting.owner_id == agreement.owner_id,
                Setting.kind == "reminder_policy",
                Setting.deleted_at.is_(None),
            )
        )
        offsets = policy.data.get("offset_minutes", [60]) if policy else [60]
        reminder_base = deadline(data)
        if data["due"]["kind"] == "date_only":
            reminder_time = policy.data.get("date_only_time", "09:00") if policy else "09:00"
            reminder_base = datetime.combine(
                date.fromisoformat(data["due"]["date"]),
                time.fromisoformat(reminder_time),
                ZoneInfo(data["due"].get("timezone", "Europe/Minsk")),
            )
        if policy is None or policy.data.get("enabled", True):
            scheduled_times = set()
            for offset in sorted(set(offsets)):
                scheduled = max(now, reminder_base - timedelta(minutes=offset))
                if scheduled in scheduled_times:
                    continue
                scheduled_times.add(scheduled)
                db.add(
                    Reminder(
                        id=uid(),
                        agreement_id=agreement.id,
                        owner_id=agreement.owner_id,
                        organization_id=agreement.organization_id,
                        agreement_version=agreement.version,
                        scheduled_at=scheduled,
                        status="scheduled",
                    )
                )
    # If a formerly sent record becomes non-deliverable, revoke it with a tombstone.
    published = await db.scalar(
        select(OutboxEvent.id).where(OutboxEvent.agreement_id == agreement.id).limit(1)
    )
    if not deliverable and not published:
        return
    event_name = (
        event_type if deliverable else ("deleted" if event_type == "deleted" else "revoked")
    )
    payload = {
        "agreement_id": agreement.id,
        "owner_id": agreement.owner_id,
        "organization_id": agreement.organization_id,
        "version": agreement.version,
        "event_type": event_name,
        "deleted": not deliverable,
        "fields": {
            key: deepcopy(data[key])
            for key in (
                "action",
                "obligor_participant_id",
                "recipient_participant_id",
                "due",
                "priority",
                "tag_ids",
                "condition",
                "condition_resolution",
            )
            if key in data
        }
        if deliverable
        else {},
        "execution": agreement.execution if deliverable else None,
    }
    # Never deliver transcript text/evidence as a side effect.
    if "due" in payload["fields"]:
        payload["fields"]["due"].pop("original_text", None)
    event_id = uid()
    payload["event_id"] = event_id
    db.add(
        OutboxEvent(
            id=event_id,
            agreement_id=agreement.id,
            owner_id=agreement.owner_id,
            organization_id=agreement.organization_id,
            aggregate_version=agreement.version,
            event_type=event_name,
            payload=payload,
            status="pending",
            attempt=0,
            not_before=now,
            created_at=now,
        )
    )
