"""Real PostgreSQL upload replay and late-worker/cancellation regressions."""

import io
import json
import os
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from mts_backend.audio.storage import AudioStorage
from mts_backend.calls import routes
from mts_backend.core.business import BusinessError, uid, utcnow
from mts_backend.core.config import Settings
from mts_backend.db.models import (
    AudioAsset,
    AuditEvent,
    Call,
    IdempotencyRecord,
    Job,
    Organization,
    Participant,
    User,
)
from mts_backend.processing import jobs

pytestmark = pytest.mark.integration


async def setup(engine, tmp_path):
    settings = Settings(
        _env_file=None,
        audio_storage_path=str(tmp_path),
        audio_encryption_key=Fernet.generate_key().decode(),
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as db:
        org = Organization(id=uid(), name="upload job test")
        db.add(org)
        await db.flush()
        user = User(
            id=uid(),
            organization_id=org.id,
            login="audio-test-" + uid(),
            display_name="test",
            password_hash="unused",
            is_active=True,
        )
        db.add(user)
        await db.flush()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
    return settings, sessions, user, org, request


async def cleanup(sessions, user, org):
    async with sessions.begin() as db:
        for model in (IdempotencyRecord, AuditEvent, Job, AudioAsset, Participant, Call):
            await db.execute(delete(model).where(model.owner_id == user.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.execute(delete(Organization).where(Organization.id == org.id))


async def make_upload(db, user, request, key="upload-test", title="Test recording"):
    metadata = json.dumps(
        {
            "title": title,
            "call_at": "2026-10-14T10:00:00+03:00",
            "timezone": "Europe/Minsk",
            "processing_rights_confirmed": True,
            "notice_version": "v1",
        }
    )
    return await routes.upload(
        request,
        UploadFile(io.BytesIO(b"1234567890"), filename="unsafe.wav"),
        metadata,
        key,
        user,
        db,
    )


@pytest.mark.asyncio
async def test_upload_replay_conflict_range_and_owner_check(tmp_path, monkeypatch):
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    settings, sessions, user, org, request = await setup(engine, tmp_path)

    async def probe(*args):
        return {"mime": "audio/wav", "duration_ms": 1000, "channels": 1}

    monkeypatch.setattr(routes, "probe", probe)
    try:
        async with sessions() as db:
            first = await make_upload(db, user, request)
            second = await make_upload(db, user, request)
            assert first == second
            with pytest.raises(BusinessError) as exc:
                await make_upload(db, user, request, title="different")
            assert exc.value.code == "idempotency_conflict"
            await db.rollback()
            # A single original asset survives replays; content is encrypted on disk.
            assets = (
                await db.scalars(select(AudioAsset).where(AudioAsset.call_id == first["call_id"]))
            ).all()
            assert (
                len(assets) == 1
                and b"1234567890"
                not in AudioStorage(settings).path(assets[0].storage_key).read_bytes()
            )
            partial = await routes.get_audio(first["call_id"], request, "bytes=2-5", user, db)
            assert partial.status_code == 206 and partial.body == b"3456"
            assert partial.headers["Content-Range"] == "bytes 2-5/10"
            suffix = await routes.get_audio(first["call_id"], request, "bytes=-3", user, db)
            assert suffix.body == b"890"
            with pytest.raises(BusinessError) as exc:
                await routes.get_audio(first["call_id"], request, "bytes=99-", user, db)
            assert exc.value.status == 416
            stranger = SimpleNamespace(id=uid(), organization_id=org.id)
            with pytest.raises(BusinessError) as exc:
                await routes.get_audio(first["call_id"], request, None, stranger, db)
            assert exc.value.status == 404
            await db.rollback()
    finally:
        await cleanup(sessions, user, org)
        await engine.dispose()


@pytest.mark.parametrize("mode", ["reclaim", "cancel", "expire_during_work"])
@pytest.mark.asyncio
async def test_job_late_commit_cannot_restore_cancelled_or_expired_work(
    tmp_path, monkeypatch, mode
):
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    settings, sessions, user, org, request = await setup(engine, tmp_path)

    async def probe(*args):
        return {"mime": "audio/wav", "duration_ms": 1000, "channels": 1}

    monkeypatch.setattr(routes, "probe", probe)
    try:
        async with sessions() as db:
            created = await make_upload(db, user, request)
        call_id = created["call_id"]
        if mode == "reclaim":
            async with sessions.begin() as db:
                job = await db.scalar(select(Job).where(Job.call_id == call_id))
                job.status = "running"
                job.attempt = 1
                job.lease_token = "stale"
                job.lease_until = utcnow() - timedelta(seconds=1)

        async def prepare(*args):
            if mode == "cancel":
                async with sessions.begin() as db:
                    call = await db.get(Call, call_id)
                    await routes.cancel_processing(
                        call_id, routes.VersionInput(expected_version=call.version), user, db
                    )
            if mode == "expire_during_work":
                async with sessions.begin() as db:
                    job = await db.scalar(select(Job).where(Job.call_id == call_id))
                    job.lease_until = utcnow() - timedelta(seconds=1)
            return b"prepared waveform"

        monkeypatch.setattr(jobs, "prepare", prepare)
        assert await jobs.process_one(engine, settings, call_id=call_id)
        async with sessions() as db:
            call = await db.get(Call, call_id)
            job = await db.scalar(select(Job).where(Job.call_id == call_id))
            derived = (
                await db.scalars(
                    select(AudioAsset).where(
                        AudioAsset.call_id == call_id, AudioAsset.kind == "derived"
                    )
                )
            ).all()
            if mode == "reclaim":
                assert job.status == "succeeded" and job.attempt == 2
                assert call.processing_status == "blocked" and call.current_transcript_id is None
                assert len(derived) == 1
            else:
                assert job.status == "cancelled" and not derived
            assert job.lease_token is None
    finally:
        await cleanup(sessions, user, org)
        await engine.dispose()
