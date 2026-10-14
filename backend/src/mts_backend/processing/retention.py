"""Retention clears all copies of expired source text and prevents late jobs."""

from copy import deepcopy
from datetime import timedelta

from sqlalchemy import delete, select, text

from mts_backend.audio.storage import AudioStorage
from mts_backend.core.business import utcnow
from mts_backend.db.models import (
    Agreement,
    AgreementRevision,
    AnalysisRun,
    AudioAsset,
    Call,
    IdempotencyRecord,
    Job,
    MockCRMRecord,
    Notification,
    OutboxEvent,
    Participant,
    Reminder,
    Summary,
    Transcript,
)


async def erase_sources(db, call, settings, all_sources=False):
    now = utcnow()
    assets = (
        (
            await db.execute(
                select(AudioAsset).where(AudioAsset.call_id == call.id).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    cancel_jobs = all_sources
    for asset in assets:
        if all_sources or asset.expires_at and asset.expires_at <= now:
            if asset.availability == "available":
                AudioStorage(settings).delete(asset.storage_key)
            asset.availability = "deleted" if all_sources else "expired"
            cancel_jobs = True
    if cancel_jobs:
        for job in await db.scalars(select(Job).where(Job.call_id == call.id).with_for_update()):
            if job.status in {"queued", "running", "retry_wait"}:
                job.status = "cancelled"
                job.lease_token = None
                job.lease_until = None
        if not call.current_transcript_id:
            call.processing_status = "cancelled"
    expired_ids = set()
    transcripts = (
        (
            await db.execute(
                select(Transcript).where(Transcript.call_id == call.id).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    for item in transcripts:
        if all_sources or item.expires_at and item.expires_at <= now:
            item.segments = []
            item.availability = "deleted" if all_sources else "expired"
            expired_ids.add(item.id)
    for summary in (
        await db.execute(select(Summary).where(Summary.call_id == call.id).with_for_update())
    ).scalars():
        if all_sources or summary.expires_at and summary.expires_at <= now:
            summary.summary = ""
            summary.client_message_draft = ""
            summary.availability = "deleted" if all_sources else "expired"
    agreements = (
        (await db.execute(select(Agreement).where(Agreement.call_id == call.id).with_for_update()))
        .scalars()
        .all()
    )

    def strip(data, linked_source_expired=False):
        value = deepcopy(data)
        source_expired = all_sources or linked_source_expired
        for evidence in value.get("evidence", []):
            if all_sources or evidence.get("transcript_revision_id") in expired_ids:
                source_expired = True
                for key in ("quote", "context", "left_context", "right_context"):
                    evidence.pop(key, None)
                evidence["availability"] = "deleted" if all_sources else "expired"
        if source_expired:
            for key in ("source_text", "transcript_text", "context"):
                value.pop(key, None)
            if isinstance(value.get("due"), dict):
                value["due"].pop("original_text", None)
        return value

    for agreement in agreements:
        linked_source_expired = agreement.transcript_id in expired_ids
        agreement.data = strip(agreement.data, linked_source_expired)
        for revision in (
            await db.execute(
                select(AgreementRevision).where(AgreementRevision.agreement_id == agreement.id)
            )
        ).scalars():
            snapshot = deepcopy(revision.data)
            if "data" in snapshot:
                snapshot["data"] = strip(snapshot["data"], linked_source_expired)
            else:
                snapshot = strip(snapshot, linked_source_expired)
            revision.data = snapshot
    # Replay snapshots must obey the same privacy horizon as live data/history.
    if expired_ids:
        ids = {a.id: a for a in agreements}
        records = await db.scalars(
            select(IdempotencyRecord).where(IdempotencyRecord.owner_id == call.owner_id)
        )
        for record in records:
            agreement = ids.get(record.response.get("id"))
            if agreement:
                record.response = strip(record.response, agreement.transcript_id in expired_ids)
    return agreements


async def erase_call(db, call, settings):
    from mts_backend.tasks.effects import agreement_changed

    call.deleted_at = utcnow()
    call.version += 1
    call.processing_status = "cancelled"
    call.analysis_status = "cancelled"
    agreements = await erase_sources(db, call, settings, all_sources=True)
    for agreement in agreements:
        for event in (
            await db.execute(select(OutboxEvent).where(OutboxEvent.agreement_id == agreement.id))
        ).scalars():
            event.status = "cancelled"
            event.payload = {}
        agreement.version += 1
        agreement.deleted_at = utcnow()
        await agreement_changed(db, agreement, "deleted")
        # The simulator shares this database: erase its last payload immediately and
        # retain a terminal tombstone against any old webhook already in flight.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"), {"identity": agreement.id}
        )
        mock = await db.get(MockCRMRecord, agreement.id, with_for_update=True)
        published = await db.scalar(
            select(OutboxEvent.id).where(OutboxEvent.agreement_id == agreement.id).limit(1)
        )
        if mock is not None or published is not None:
            if mock is None:
                mock = MockCRMRecord(
                    agreement_id=agreement.id,
                    owner_id=agreement.owner_id,
                    organization_id=agreement.organization_id,
                    event_ids=[],
                    version=agreement.version,
                )
                db.add(mock)
            mock.version = max(mock.version, agreement.version)
            mock.deleted = True
            mock.terminal = True
            mock.payload = {}
            mock.updated_at = utcnow()
        await db.execute(delete(Notification).where(Notification.agreement_id == agreement.id))
        for reminder in await db.scalars(
            select(Reminder).where(
                Reminder.agreement_id == agreement.id, Reminder.status == "scheduled"
            )
        ):
            reminder.status = "cancelled"
        agreement.data = {}
        for revision in (
            await db.execute(
                select(AgreementRevision).where(AgreementRevision.agreement_id == agreement.id)
            )
        ).scalars():
            revision.data = {}
        for event in (
            await db.execute(select(OutboxEvent).where(OutboxEvent.agreement_id == agreement.id))
        ).scalars():
            if event.aggregate_version != agreement.version:
                event.status = "cancelled"
                event.payload = {}
    for run in await db.scalars(select(AnalysisRun).where(AnalysisRun.call_id == call.id)):
        run.settings_snapshot = {}
    for participant in (
        await db.execute(select(Participant).where(Participant.call_id == call.id))
    ).scalars():
        participant.display_name = None
    call.title = "Deleted call"
    call.client_id = None
    # Stored responses must not bypass retention by replaying old business fields.
    records = (
        (
            await db.execute(
                select(IdempotencyRecord).where(IdempotencyRecord.owner_id == call.owner_id)
            )
        )
        .scalars()
        .all()
    )
    ids = {a.id for a in agreements}
    for record in records:
        if record.response.get("call_id") == call.id or record.response.get("id") in ids:
            await db.delete(record)


async def sweep(db, settings):
    calls = (
        (
            await db.execute(
                select(Call).where(Call.deleted_at.is_(None)).with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for call in calls:
        if call.created_at + timedelta(days=settings.business_retention_days) <= utcnow():
            await erase_call(db, call, settings)
        else:
            await erase_sources(db, call, settings)
    for row in (
        await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.created_at < utcnow() - timedelta(hours=24)
            )
        )
    ).scalars():
        await db.delete(row)
