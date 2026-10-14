"""PostgreSQL jobs with bounded leases and separate computation transactions."""

import asyncio
import hashlib
import tempfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mts_backend.audio.probe import prepare
from mts_backend.audio.storage import AudioStorage
from mts_backend.core.business import BusinessError, uid, utcnow
from mts_backend.db.models import AudioAsset, Call, Job


def claimable(job, now):
    return (job.status in {"queued", "retry_wait"} and job.not_before <= now) or (
        job.status == "running" and job.lease_until is not None and job.lease_until < now
    )


def expired(asset, now):
    return asset.availability != "available" or (
        asset.expires_at is not None and asset.expires_at <= now
    )


async def process_one(engine, settings, call_id=None):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uid()
    async with sessions.begin() as db:
        now = utcnow()
        query = (
            select(Job)
            .where(
                or_(
                    and_(Job.status.in_(["queued", "retry_wait"]), Job.not_before <= now),
                    and_(Job.status == "running", Job.lease_until < now),
                )
            )
            .order_by(Job.created_at, Job.id)
            .limit(1)
        )
        if call_id is not None:
            query = query.where(Job.call_id == call_id)
        candidate = await db.scalar(query)
        if not candidate:
            return False
        # Use Call→Job→Asset everywhere, matching cancellation/deletion transactions.
        call = await db.get(Call, candidate.call_id, with_for_update=True)
        job = await db.scalar(
            select(Job)
            .where(Job.id == candidate.id)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if not job or not claimable(job, utcnow()):
            return False
        if job.attempt >= job.max_attempts:
            job.status = "failed"
            job.error_code = "attempts_exhausted"
            call.processing_status = "failed"
            call.version += 1
            return True
        asset = await db.scalar(
            select(AudioAsset)
            .where(AudioAsset.call_id == job.call_id, AudioAsset.kind == "original")
            .with_for_update()
        )
        if call.deleted_at or not asset or expired(asset, now):
            job.status = "cancelled"
            call.processing_status = "cancelled"
            call.version += 1
            return True
        job.status = "running"
        job.attempt += 1
        job.lease_token = token
        job.lease_until = now + timedelta(seconds=settings.job_lease_seconds)
        call.processing_status = "preparing"
        call.version += 1
        job_id, asset_key, selected_call_id = job.id, asset.storage_key, call.id

    async def heartbeat():
        while True:
            await asyncio.sleep(settings.job_lease_seconds / 3)
            async with sessions.begin() as db:
                current = await db.get(Job, job_id, with_for_update=True)
                if current.status != "running" or current.lease_token != token:
                    return
                current.lease_until = utcnow() + timedelta(seconds=settings.job_lease_seconds)

    renewal = asyncio.create_task(heartbeat())
    new_key, reason = None, None
    try:
        storage = AudioStorage(settings)
        raw = await asyncio.to_thread(storage.read, asset_key)
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "input"
            original.write_bytes(raw)
            content = await prepare(original, Path(temp) / "prepared.wav", settings)
        new_key = uid()
        await asyncio.to_thread(storage.write, new_key, content)
    except BusinessError as exc:
        reason = exc.code
    except Exception:
        reason = "preparation_failed"
    finally:
        renewal.cancel()
        try:
            await renewal
        except asyncio.CancelledError:
            pass
    async with sessions.begin() as db:
        call = await db.get(Call, selected_call_id, with_for_update=True)
        job = await db.get(Job, job_id, with_for_update=True)
        asset = await db.scalar(
            select(AudioAsset).where(AudioAsset.storage_key == asset_key).with_for_update()
        )
        lease_current = (
            job.lease_token == token
            and job.status == "running"
            and job.lease_until is not None
            and job.lease_until > utcnow()
        )
        if not lease_current or call.deleted_at or not asset or expired(asset, utcnow()):
            if new_key:
                AudioStorage(settings).delete(new_key)
            if job.lease_token == token:
                job.status = "cancelled"
                job.lease_token = None
                job.lease_until = None
                call.processing_status = "cancelled"
                call.version += 1
            return True
        job.lease_token = None
        job.lease_until = None
        if reason:
            job.error_code = reason
            permanent = reason in {
                "silent_audio",
                "invalid_audio",
                "source_expired",
                "storage_not_configured",
                "decoder_unavailable",
            }
            job.status = "failed" if permanent or job.attempt >= job.max_attempts else "retry_wait"
            job.not_before = utcnow() + timedelta(seconds=2**job.attempt)
            call.processing_status = "failed" if job.status == "failed" else "queued"
        else:
            previous = (
                await db.scalars(
                    select(AudioAsset).where(
                        AudioAsset.call_id == selected_call_id, AudioAsset.kind == "derived"
                    )
                )
            ).all()
            for old in previous:
                AudioStorage(settings).delete(old.storage_key)
                await db.delete(old)
            db.add(
                AudioAsset(
                    call_id=selected_call_id,
                    owner_id=call.owner_id,
                    organization_id=call.organization_id,
                    kind="derived",
                    storage_key=new_key,
                    mime="audio/wav",
                    sha256=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                    duration_ms=asset.duration_ms,
                    channels=1,
                    expires_at=asset.expires_at,
                )
            )
            job.status = "succeeded"
            job.error_code = None
            call.processing_status = "blocked"
            # No ASR provider: preparation must not fabricate transcript/analysis.
        call.version += 1
    return True
