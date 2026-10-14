import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from mts_backend.core.business import BusinessError, uid, utcnow
from mts_backend.db.models import (
    Agreement,
    Call,
    DeliveryAttempt,
    MockCRMRecord,
    Notification,
    Organization,
    OutboxEvent,
    Reminder,
    User,
)
from mts_backend.integrations.delivery import deliver_once
from mts_backend.integrations.mock_crm import CRMEvent, apply_event
from mts_backend.reminders.service import notify_due
from mts_backend.settings.routes import SettingWrite, save_setting, snapshot_settings
from mts_backend.tasks.effects import agreement_changed
from mts_backend.tasks.query import TaskFilters, select_tasks
from mts_backend.tasks.routes import ExecutionAction, execute

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def context(monkeypatch):
    url = os.getenv("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL required.")
    from mts_backend.core.config import get_settings

    monkeypatch.setenv(
        "MTS_DATA_ENCRYPTION_KEY",
        os.getenv("MTS_DATA_ENCRYPTION_KEY") or Fernet.generate_key().decode(),
    )
    get_settings.cache_clear()
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        outer = await connection.begin()
        async with AsyncSession(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as db:
            org = Organization(id=uid(), name="Tasks fixture")
            db.add(org)
            await db.flush()
            user = User(
                id=uid(),
                organization_id=org.id,
                login=uid(),
                display_name="Tester",
                password_hash="unused",
                is_active=True,
            )
            db.add(user)
            await db.flush()
            call = Call(
                id=uid(),
                owner_id=user.id,
                organization_id=org.id,
                title="Fixture",
                call_at=utcnow(),
                timezone="Europe/Minsk",
                is_demo=True,
            )
            db.add(call)
            await db.flush()
            agreement = Agreement(
                id=uid(),
                call_id=call.id,
                owner_id=user.id,
                organization_id=org.id,
                verification="accepted",
                execution="open",
                version=1,
                accepted_at=utcnow(),
                source="manual",
                data={
                    "action": "Prepare quotation",
                    "priority": "normal",
                    "due": {
                        "kind": "instant",
                        "at": (utcnow() + timedelta(minutes=5)).isoformat(),
                        "timezone": "Europe/Minsk",
                    },
                    "needs_details": [],
                    "obligor_participant_id": uid(),
                    "recipient_participant_id": uid(),
                    "tag_ids": [],
                },
            )
            db.add(agreement)
            await db.flush()
            yield db, user, agreement
            await db.rollback()
        await outer.rollback()
    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_atomic_effects_cancel_stale_reminders_and_revoke(context):
    db, user, item = context
    await agreement_changed(db, item, "agreement.accept")
    await db.flush()
    assert (
        len(list(await db.scalars(select(Reminder).where(Reminder.agreement_id == item.id)))) == 1
    )
    first = await db.scalar(select(OutboxEvent).where(OutboxEvent.agreement_id == item.id))
    assert first.payload["fields"]["action"] == "Prepare quotation"
    assert "evidence" not in first.payload["fields"]
    assert "original_text" not in first.payload["fields"]["due"]
    item.version = 2
    item.verification = "proposed"
    await agreement_changed(db, item, "agreement.unconfirm")
    await db.flush()
    reminders = list(await db.scalars(select(Reminder).where(Reminder.agreement_id == item.id)))
    assert all(x.status == "cancelled" for x in reminders)
    events = list(await db.scalars(select(OutboxEvent).where(OutboxEvent.agreement_id == item.id)))
    assert any(x.payload["deleted"] and x.payload["fields"] == {} for x in events)
    assert (
        await select_tasks(db, user, TaskFilters(execution=[], tag_id=[], agreement_ids=[])) == []
    )


@pytest.mark.asyncio
async def test_due_notifications_are_unique_and_old_revision_is_cancelled(context):
    db, _, item = context
    await agreement_changed(db, item, "accepted")
    await db.flush()
    assert await notify_due(db, SimpleNamespace()) == 1
    assert await notify_due(db, SimpleNamespace()) == 0
    assert (
        len(
            list(await db.scalars(select(Notification).where(Notification.agreement_id == item.id)))
        )
        == 1
    )
    stale = Reminder(
        id=uid(),
        agreement_id=item.id,
        owner_id=item.owner_id,
        organization_id=item.organization_id,
        agreement_version=0,
        status="scheduled",
        scheduled_at=utcnow() - timedelta(seconds=1),
    )
    db.add(stale)
    await db.flush()
    assert await notify_due(db, SimpleNamespace()) == 0
    assert stale.status == "cancelled"


@pytest.mark.asyncio
async def test_unknown_due_never_publishes_and_settings_snapshot_is_versioned(context):
    db, user, item = context
    item.data = {**item.data, "due": {"kind": "unknown"}}
    await agreement_changed(db, item, "accepted")
    await db.flush()
    assert (
        await db.scalar(select(OutboxEvent.id).where(OutboxEvent.agreement_id == item.id)) is None
    )
    item.data = {
        **item.data,
        "due": {
            "kind": "instant",
            "at": utcnow().isoformat(),
            "timezone": "Europe/Minsk",
            "ambiguous": True,
        },
    }
    await agreement_changed(db, item, "accepted")
    await db.flush()
    assert (
        await db.scalar(select(OutboxEvent.id).where(OutboxEvent.agreement_id == item.id)) is None
    )
    rule = await save_setting(db, user, "trigger", SettingWrite(phrase="Обещаю"))
    snapshot = await snapshot_settings(db, user)
    await save_setting(
        db, user, "trigger", SettingWrite(expected_version=1, phrase="Пришлю"), rule["id"]
    )
    assert snapshot["items"][0]["phrase"] == "Обещаю"
    assert (await snapshot_settings(db, user))["items"][0]["version"] == 2


@pytest.mark.asyncio
async def test_mock_crm_deduplicates_and_older_event_cannot_resurrect_tombstone(context):
    db, _, item = context
    base = dict(
        agreement_id=item.id,
        owner_id=item.owner_id,
        organization_id=item.organization_id,
        version=1,
        event_type="accepted",
        fields={"action": "Prepare"},
    )
    event = CRMEvent(event_id=uid(), **base)
    assert (await apply_event(db, event))["status"] == "applied"
    assert (await apply_event(db, event))["status"] == "duplicate"
    assert (
        await apply_event(
            db,
            CRMEvent(
                event_id=uid(),
                **{**base, "version": 2, "deleted": True, "event_type": "revoked", "fields": {}},
            ),
        )
    )["deleted"]
    assert (await apply_event(db, CRMEvent(event_id=uid(), **base)))["status"] == "stale"
    row = await db.get(MockCRMRecord, item.id)
    assert row.deleted and row.payload == {} and row.version == 2
    terminal = CRMEvent(
        event_id=uid(),
        **{**base, "version": 3, "deleted": True, "event_type": "deleted", "fields": {}},
    )
    assert (await apply_event(db, terminal))["deleted"]
    late = CRMEvent(event_id=uid(), **{**base, "version": 99})
    assert (await apply_event(db, late))["status"] == "terminal_deleted"
    assert row.deleted and row.payload == {} and row.version == 3 and row.terminal


@pytest.mark.asyncio
async def test_delivery_records_attempt_without_external_http(context, monkeypatch):
    db, _, item = context
    await agreement_changed(db, item, "accepted")
    await db.flush()
    event = await db.scalar(select(OutboxEvent).where(OutboxEvent.agreement_id == item.id))
    event.created_at = datetime(1900, 1, 1, tzinfo=UTC)
    await db.flush()
    monkeypatch.setattr(
        "mts_backend.integrations.delivery.send_local", lambda *args: (200, "success")
    )
    config = SimpleNamespace(
        crm_webhook_url="http://127.0.0.1:8001/webhook",
        crm_webhook_token="test",
        crm_max_attempts=3,
    )
    # Older global rows from other test fixtures are not eligible in this rollback transaction.
    await deliver_once(db, config)
    rows = list(
        await db.scalars(
            select(DeliveryAttempt)
            .join(OutboxEvent)
            .where(
                OutboxEvent.agreement_id == item.id,
            )
        )
    )
    assert rows and rows[0].response_code == 200


@pytest.mark.asyncio
async def test_execution_replay_conflict_and_reopen(context):
    db, user, item = context
    body = ExecutionAction(expected_version=1, action="complete")
    completed = await execute(item.id, body, "complete-once", user, db)
    assert completed["execution"] == "done" and completed["version"] == 2
    replay = await execute(item.id, body, "complete-once", user, db)
    assert replay == completed and item.version == 2
    with pytest.raises(BusinessError) as caught:
        await execute(
            item.id, ExecutionAction(expected_version=2, action="reopen"), "complete-once", user, db
        )
    assert caught.value.code == "idempotency_conflict"
    reopened = await execute(
        item.id, ExecutionAction(expected_version=2, action="reopen"), "reopen-once", user, db
    )
    assert reopened["execution"] == "open" and reopened["version"] == 3


@pytest.mark.asyncio
async def test_retry_is_bounded_and_later_attempts_are_recorded(context, monkeypatch):
    db, _, item = context
    await agreement_changed(db, item, "accepted")
    await db.flush()
    monkeypatch.setattr(
        "mts_backend.integrations.delivery.send_local", lambda *args: (None, "network_error")
    )
    config = SimpleNamespace(
        crm_webhook_url="http://127.0.0.1:8001/webhook",
        crm_webhook_token="test",
        crm_max_attempts=3,
    )
    event = await db.scalar(select(OutboxEvent).where(OutboxEvent.agreement_id == item.id))
    event.created_at = datetime(1900, 1, 1, tzinfo=UTC)
    for _ in range(3):
        event.not_before = utcnow() - timedelta(seconds=1)
        await db.flush()
        await deliver_once(db, config)
    assert event.status == "failed" and event.attempt == 3
    attempts = list(
        await db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.event_id == event.id))
    )
    assert len(attempts) == 3 and all(x.result == "network_error" for x in attempts)
