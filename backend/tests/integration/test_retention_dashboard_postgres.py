"""Source-retention, deletion tombstone and honest dashboard regression tests."""

import os
from copy import deepcopy
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mts_backend.agreements.routes import edit_agreement, transition
from mts_backend.agreements.schemas import AgreementEdit, AgreementTransition
from mts_backend.analysis.fixtures import get_scenario
from mts_backend.analysis.service import initialize_demo
from mts_backend.core.business import uid, utcnow
from mts_backend.core.config import Settings
from mts_backend.dashboard.routes import dashboard
from mts_backend.db.models import (
    Agreement,
    AgreementRevision,
    Call,
    IdempotencyRecord,
    Job,
    MockCRMRecord,
    Notification,
    Organization,
    OutboxEvent,
    Reminder,
    Summary,
    Transcript,
    User,
)
from mts_backend.integrations.mock_crm import CRMEvent, apply_event
from mts_backend.processing.retention import erase_call, erase_sources

pytestmark = pytest.mark.integration


async def owned_data(db):
    org = Organization(id=uid(), name="retention dashboard test")
    db.add(org)
    await db.flush()
    user = User(
        id=uid(),
        organization_id=org.id,
        login="retention-test-" + uid(),
        display_name="test",
        password_hash="unused",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    scenario = get_scenario("syn_01")
    call = Call(
        id=uid(),
        owner_id=user.id,
        organization_id=org.id,
        title="Test",
        call_at=utcnow(),
        timezone="Europe/Minsk",
        language="ru",
        source="demo",
        is_demo=True,
        scenario_id=scenario["id"],
        version=1,
    )
    db.add(call)
    await db.flush()
    await initialize_demo(db, call, scenario)
    agreement = await db.scalar(select(Agreement).where(Agreement.call_id == call.id))
    return user, call, agreement


@pytest.mark.asyncio
async def test_expired_text_scrubs_every_copy_but_keeps_accepted_task_editable():
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            async with async_sessionmaker(conn, expire_on_commit=False)() as db:
                user, call, agreement = await owned_data(db)
                accepted = await transition(
                    agreement.id,
                    "accept",
                    AgreementTransition(expected_version=1),
                    "retained-accept",
                    db,
                    user,
                )
                raw_quote = accepted["evidence"][0]["quote"]
                await edit_agreement(
                    agreement.id,
                    AgreementEdit(expected_version=2, action="Keep task", confirm_changes=True),
                    db,
                    user,
                )
                source = await db.get(Transcript, call.current_transcript_id)
                summary = await db.get(Summary, call.current_summary_id)
                source.expires_at = summary.expires_at = utcnow() - timedelta(seconds=1)
                await erase_sources(db, call, Settings(_env_file=None))
                assert source.segments == [] and source.availability == "expired"
                assert summary.summary == summary.client_message_draft == ""
                assert (
                    agreement.verification == "accepted" and agreement.data["action"] == "Keep task"
                )
                assert "original_text" not in agreement.data["due"]
                revisions = (
                    await db.scalars(
                        select(AgreementRevision).where(
                            AgreementRevision.agreement_id == agreement.id
                        )
                    )
                ).all()
                assert len(revisions) == 3
                assert all(raw_quote not in str(r.data) for r in revisions)
                idem = await db.scalar(
                    select(IdempotencyRecord).where(IdempotencyRecord.owner_id == user.id)
                )
                assert raw_quote not in str(idem.response)
                edited = await edit_agreement(
                    agreement.id,
                    AgreementEdit(
                        expected_version=3, action="Still editable", confirm_changes=True
                    ),
                    db,
                    user,
                )
                assert edited["action"] == "Still editable"
                assert all("quote" not in e for e in edited["evidence"])
            await tx.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_full_delete_cancels_no_audio_job_and_terminal_crm_prevents_resurrection():
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            async with async_sessionmaker(conn, expire_on_commit=False)() as db:
                user, call, agreement = await owned_data(db)
                await transition(
                    agreement.id,
                    "accept",
                    AgreementTransition(expected_version=1),
                    "delete-accept",
                    db,
                    user,
                )
                event = await db.scalar(
                    select(OutboxEvent).where(OutboxEvent.agreement_id == agreement.id)
                )
                stale = CRMEvent.model_validate(deepcopy(event.payload))
                await apply_event(db, stale)
                job = Job(
                    id=uid(),
                    call_id=call.id,
                    owner_id=user.id,
                    organization_id=user.organization_id,
                    stage="prepare",
                    status="running",
                    lease_token="running",
                    lease_until=utcnow() + timedelta(minutes=1),
                )
                db.add(job)
                await db.flush()
                await erase_call(db, call, Settings(_env_file=None))
                await db.flush()
                assert (
                    job.status == "cancelled"
                    and job.lease_token is None
                    and job.lease_until is None
                )
                assert agreement.data == {} and agreement.deleted_at is not None
                assert call.deleted_at is not None
                assert not (
                    await db.scalars(
                        select(Notification).where(Notification.agreement_id == agreement.id)
                    )
                ).all()
                assert all(
                    r.status != "scheduled"
                    for r in await db.scalars(
                        select(Reminder).where(Reminder.agreement_id == agreement.id)
                    )
                )
                revisions = (
                    await db.scalars(
                        select(AgreementRevision).where(
                            AgreementRevision.agreement_id == agreement.id
                        )
                    )
                ).all()
                assert all(r.data == {} for r in revisions)
                mock = await db.get(MockCRMRecord, agreement.id)
                assert mock.deleted and mock.terminal and mock.payload == {}
                stale.event_id = uid()
                stale.version = agreement.version + 100
                assert (await apply_event(db, stale))["status"] == "terminal_deleted"
                events = (
                    await db.scalars(
                        select(OutboxEvent).where(OutboxEvent.agreement_id == agreement.id)
                    )
                ).all()
                assert any(e.event_type == "deleted" and e.payload.get("deleted") for e in events)
                assert all(
                    e.payload == {} for e in events if e.aggregate_version != agreement.version
                )
            await tx.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_owner_demo_cohort_and_unmeasured_savings():
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            async with async_sessionmaker(conn, expire_on_commit=False)() as db:
                user, call, proposal = await owned_data(db)
                _, other_call, other_agreement = await owned_data(db)
                for execution in ("open", "done", "cancelled"):
                    data = deepcopy(proposal.data)
                    data["due"] = {
                        "kind": "date_only",
                        "date": "2000-01-01",
                        "timezone": "Europe/Minsk",
                    }
                    db.add(
                        Agreement(
                            id=uid(),
                            call_id=call.id,
                            owner_id=user.id,
                            organization_id=user.organization_id,
                            source="manual",
                            data=data,
                            verification="accepted",
                            execution=execution,
                            accepted_at=utcnow(),
                            version=1,
                        )
                    )
                other_agreement.verification = "accepted"
                other_agreement.execution = "done"
                other_agreement.accepted_at = utcnow()
                await db.flush()
                stats = await dashboard(mode="demo", user=user, db=db)
                assert stats["agreements_count"] == 3 and stats["completed_count"] == 1
                assert stats["cancelled_count"] == 1 and stats["completion_denominator"] == 2
                assert stats["completion_rate"] == 0.5 and stats["overdue_count"] == 1
                assert stats["proposed_count"] == 1
                assert (
                    stats["saved_time"]["seconds"] is None
                    and stats["model_accuracy"] == "not_measured"
                )
                real = await dashboard(mode="real", user=user, db=db)
                assert real["agreements_count"] == 0 and real["completion_rate"] is None
                future = await dashboard(mode="demo", accepted_from="2099-01-01", user=user, db=db)
                assert future["agreements_count"] == 0
            await tx.rollback()
    finally:
        await engine.dispose()
