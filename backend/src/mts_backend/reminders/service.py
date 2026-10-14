from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from mts_backend.core.business import uid, utcnow
from mts_backend.db.models import Agreement, Call, Notification, Reminder, Setting


def after_quiet_hours(now, policy):
    quiet = policy.get("quiet_hours")
    if not quiet or quiet["start"] == quiet["end"]:
        return now
    local = now.astimezone(ZoneInfo(policy.get("timezone", "Europe/Minsk")))
    start, end = quiet["start"], quiet["end"]
    hour = local.hour
    active = start <= hour < end if start < end else hour >= start or hour < end
    if not active:
        return now
    target = local.replace(hour=end, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target


async def notify_due(db, settings):
    now = utcnow()
    rows = list(
        await db.scalars(
            select(Reminder)
            .where(
                Reminder.status == "scheduled",
                Reminder.scheduled_at <= now,
            )
            .order_by(Reminder.scheduled_at, Reminder.id)
            .limit(30)
            .with_for_update(skip_locked=True)
        )
    )
    count = 0
    for item in rows:
        agreement = await db.get(Agreement, item.agreement_id, with_for_update=True)
        call = await db.get(Call, agreement.call_id) if agreement else None
        if (
            agreement is None
            or call is None
            or call.deleted_at is not None
            or agreement.deleted_at is not None
            or agreement.verification != "accepted"
            or agreement.version != item.agreement_version
            or agreement.execution not in {"open", "in_progress"}
        ):
            item.status = "cancelled"
            continue
        policy = await db.scalar(
            select(Setting).where(
                Setting.owner_id == item.owner_id,
                Setting.kind == "reminder_policy",
                Setting.deleted_at.is_(None),
            )
        )
        if policy and not policy.data.get("enabled", True):
            item.status = "cancelled"
            continue
        allowed_at = after_quiet_hours(now, policy.data if policy else {})
        if allowed_at > now:
            collision = await db.scalar(
                select(Reminder.id).where(
                    Reminder.agreement_id == item.agreement_id,
                    Reminder.agreement_version == item.agreement_version,
                    Reminder.scheduled_at == allowed_at,
                    Reminder.id != item.id,
                )
            )
            if collision:
                item.status = "cancelled"
            else:
                item.scheduled_at = allowed_at
                await db.flush()
            continue
        key = "reminder:" + item.id
        existing = await db.scalar(
            select(Notification.id).where(Notification.deduplication_key == key)
        )
        if existing is None:
            db.add(
                Notification(
                    id=uid(),
                    owner_id=item.owner_id,
                    organization_id=item.organization_id,
                    agreement_id=item.agreement_id,
                    kind="reminder",
                    version=1,
                    deduplication_key=key,
                    created_at=now,
                )
            )
            count += 1
        item.status = "sent"
    await db.flush()
    return count
