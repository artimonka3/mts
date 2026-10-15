# ruff: noqa: B008 - FastAPI dependency defaults.
"""Calls, upload, demo import, audio retrieval and processing control."""

import hashlib
import json
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import select, text
from starlette.responses import Response

from mts_backend.audio.probe import probe
from mts_backend.audio.storage import AudioStorage
from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, uid, utcnow, version_check
from mts_backend.db.models import AudioAsset, Call, Client, IdempotencyRecord, Job, Participant
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["calls"])


class ParticipantInput(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    role: Literal["manager", "client", "other", "unknown"] = "unknown"


class Metadata(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    call_at: AwareDatetime
    timezone: str = "Europe/Minsk"
    language: Literal["ru"] = "ru"
    source: Literal["upload", "browser_recording"] = "upload"
    client_id: str | None = None
    participants: list[ParticipantInput] = Field(default_factory=list, max_length=20)
    processing_rights_confirmed: bool
    notice_version: str = Field(min_length=1, max_length=80)

    @field_validator("timezone")
    @classmethod
    def timezone_known(cls, v):
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown timezone.") from None
        return v


class DemoInput(BaseModel):
    scenario_id: str = "syn_01"
    client_id: str | None = None


class VersionInput(BaseModel):
    expected_version: int = Field(ge=1)


class CallPatch(VersionInput):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    client_id: str | None = None
    participants: list[ParticipantInput] | None = Field(default=None, max_length=20)


class RetryInput(VersionInput):
    stage: Literal["prepare"] = "prepare"


def serialize_call(c):
    return {
        k: getattr(c, k)
        for k in (
            "id",
            "client_id",
            "title",
            "call_at",
            "timezone",
            "language",
            "source",
            "is_demo",
            "scenario_id",
            "processing_status",
            "analysis_status",
            "current_transcript_id",
            "current_summary_id",
            "version",
            "created_at",
        )
    } | {
        "provenance": {"source": "fixture" if c.is_demo else c.source, "is_demo": c.is_demo},
        "capabilities": {"asr": "disabled", "llm": "disabled", "manual_transcript": True},
    }


async def replay(db, user, operation, key, digest):
    if not key or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
        raise BusinessError(400, "idempotency_key_required", "Provide a valid Idempotency-Key.")
    # Advisory lock serializes duplicate creation without holding audio decoding transaction.
    lock = int.from_bytes(
        hashlib.sha256(f"{user.id}:{operation}:{key}".encode()).digest()[:8], "big", signed=True
    )
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    record = (
        await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.owner_id == user.id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == key,
            )
        )
    ).scalar_one_or_none()
    if record:
        if record.digest != digest:
            raise BusinessError(409, "idempotency_conflict", "Key has a different request.")
        await owned(db, Call, record.response["call_id"], user)
        return record.response
    return None


def remember(db, user, operation, key, digest, result):
    db.add(
        IdempotencyRecord(
            owner_id=user.id,
            operation=operation,
            key=key,
            digest=digest,
            response=result,
            status_code=202,
        )
    )


@router.post("/calls", status_code=202)
async def upload(
    request: Request,
    audio: UploadFile = File(),
    metadata: str = Form(),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(current_user),
    db=Depends(get_db),
):
    try:
        m = Metadata.model_validate_json(metadata)
    except Exception:
        raise BusinessError(422, "validation_error", "Invalid call metadata.") from None
    if not m.processing_rights_confirmed:
        raise BusinessError(
            422, "processing_rights_required", "Confirm the right to process the recording."
        )
    if m.call_at.astimezone(ZoneInfo(m.timezone)).utcoffset() != m.call_at.utcoffset():
        raise BusinessError(422, "timezone_offset_mismatch", "Call offset does not match timezone.")
    settings = request.app.state.settings
    content = bytearray()
    while chunk := await audio.read(65536):
        content.extend(chunk)
        if len(content) > settings.upload_max_bytes:
            raise BusinessError(413, "payload_too_large", "Audio is too large.")
    if not content:
        raise BusinessError(422, "invalid_audio", "Audio is empty.")
    digest = hashlib.sha256(m.model_dump_json().encode() + bytes(content)).hexdigest()
    prior = await replay(db, user, "upload", key, digest)
    if prior:
        return prior
    if m.client_id:
        await owned(db, Client, m.client_id, user)
    # Never trust filename; decoder sees a private file with a generated name.
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / "input"
        raw.write_bytes(content)
        info = await probe(raw, settings)
    call = Call(
        id=uid(),
        owner_id=user.id,
        organization_id=user.organization_id,
        **m.model_dump(exclude={"participants"}),
        processing_status="queued",
    )
    db.add(call)
    await db.flush()
    asset_key = uid()
    storage = AudioStorage(settings)
    storage.write(asset_key, bytes(content))
    try:
        db.add(
            AudioAsset(
                call_id=call.id,
                owner_id=user.id,
                organization_id=user.organization_id,
                kind="original",
                storage_key=asset_key,
                sha256=hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
                **info,
                expires_at=utcnow() + timedelta(days=settings.audio_retention_days),
            )
        )
        db.add(
            Job(
                call_id=call.id,
                owner_id=user.id,
                organization_id=user.organization_id,
                stage="prepare",
            )
        )
        for p in m.participants:
            db.add(
                Participant(
                    call_id=call.id,
                    owner_id=user.id,
                    organization_id=user.organization_id,
                    **p.model_dump(),
                )
            )
        result = {
            "call_id": call.id,
            "processing_url": f"/api/v1/calls/{call.id}/processing",
            "version": call.version,
        }
        remember(db, user, "upload", key, digest, result)
        await audit(db, user, call, "upload", [])
        await db.flush()
        await db.commit()
        return result
    except BaseException:
        storage.delete(asset_key)
        raise


@router.post("/demo/calls", status_code=202)
async def demo(
    body: DemoInput,
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(current_user),
    db=Depends(get_db),
):
    from mts_backend.analysis.service import initialize_demo

    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    previous = await replay(db, user, "demo", key, digest)
    if previous:
        return previous
    if body.client_id:
        await owned(db, Client, body.client_id, user)
    fixture = json.loads(Path(request.app.state.settings.fixture_path).read_text())
    scenario = next((x for x in fixture["dialogues"] if x["id"] == body.scenario_id), None)
    if scenario is None:
        raise BusinessError(404, "not_found", "Scenario not found.")
    call = Call(
        id=uid(),
        owner_id=user.id,
        organization_id=user.organization_id,
        client_id=body.client_id,
        title=scenario["title"],
        call_at=datetime.fromisoformat(scenario["call_at"]),
        timezone=scenario["timezone"],
        language="ru",
        source="demo",
        is_demo=True,
        scenario_id=body.scenario_id,
    )
    db.add(call)
    await db.flush()
    await initialize_demo(
        db, call, scenario, retention_days=request.app.state.settings.text_retention_days
    )
    result = {
        "call_id": call.id,
        "processing_url": f"/api/v1/calls/{call.id}/processing",
        "version": call.version,
    }
    remember(db, user, "demo", key, digest, result)
    await audit(db, user, call, "demo_create", [])
    return result


@router.get("/calls")
async def list_calls(
    limit: int = 20,
    offset: int = 0,
    client_id: str | None = None,
    is_demo: bool | None = None,
    user=Depends(current_user),
    db=Depends(get_db),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise BusinessError(422, "validation_error", "Invalid pagination.")
    q = (
        select(Call)
        .where(
            Call.owner_id == user.id,
            Call.organization_id == user.organization_id,
            Call.deleted_at.is_(None),
        )
        .order_by(Call.created_at.desc(), Call.id.desc())
    )
    if client_id:
        q = q.where(Call.client_id == (await owned(db, Client, client_id, user)).id)
    if is_demo is not None:
        q = q.where(Call.is_demo == is_demo)
    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [serialize_call(c) for c in rows[offset : offset + limit]],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/calls/{call_id}")
async def get_call(call_id: str, user=Depends(current_user), db=Depends(get_db)):
    call = await owned(db, Call, call_id, user)
    data = serialize_call(call)
    people = (
        (await db.execute(select(Participant).where(Participant.call_id == call.id)))
        .scalars()
        .all()
    )
    data["participants"] = [
        {k: getattr(p, k) for k in ("id", "display_name", "role", "speaker_id")} for p in people
    ]
    await audit(db, user, call, "read", [])
    return data


@router.patch("/calls/{call_id}")
async def patch_call(call_id: str, body: CallPatch, user=Depends(current_user), db=Depends(get_db)):
    call = await owned(db, Call, call_id, user)
    version_check(call, body.expected_version)
    fields = body.model_fields_set - {"expected_version", "participants"}
    if "client_id" in fields and body.client_id:
        await owned(db, Client, body.client_id, user)
    if "title" in fields and body.title is None:
        raise BusinessError(422, "validation_error", "Title cannot be null.")
    for k in fields:
        setattr(call, k, getattr(body, k))
    if body.participants is not None:
        # Append-only participant IDs preserve prior evidence references.
        for person in body.participants:
            db.add(
                Participant(
                    call_id=call.id,
                    owner_id=user.id,
                    organization_id=user.organization_id,
                    **person.model_dump(),
                )
            )
    call.version += 1
    await audit(db, user, call, "edit", fields)
    return serialize_call(call)


@router.get("/calls/{call_id}/audio")
async def get_audio(
    call_id: str,
    request: Request,
    range_header: str | None = Header(default=None, alias="Range"),
    user=Depends(current_user),
    db=Depends(get_db),
):
    call = await owned(db, Call, call_id, user)
    asset = (
        await db.execute(
            select(AudioAsset).where(AudioAsset.call_id == call.id, AudioAsset.kind == "original")
        )
    ).scalar_one_or_none()
    if not asset:
        raise BusinessError(404, "not_found", "This call has no real audio.")
    if asset.availability != "available" or asset.expires_at and asset.expires_at <= utcnow():
        raise BusinessError(410, "source_expired", "Audio has expired.")
    content = AudioStorage(request.app.state.settings).read(asset.storage_key)
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
        "Content-Disposition": 'inline; filename="recording"',
    }
    status = 200
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        if not match or not any(match.groups()):
            raise BusinessError(416, "invalid_range", "Invalid byte range.")
        a, b = match.groups()
        start = int(a) if a else max(0, len(content) - int(b))
        end = int(b) if a and b else len(content) - 1
        if start >= len(content) or end < start:
            raise BusinessError(416, "invalid_range", "Invalid byte range.")
        end = min(end, len(content) - 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{len(content)}"
        content = content[start : end + 1]
        status = 206
    await audit(db, user, call, "audio_read", [])
    return Response(content, status_code=status, media_type=asset.mime, headers=headers)


@router.get("/calls/{call_id}/processing")
async def processing(call_id: str, user=Depends(current_user), db=Depends(get_db)):
    call = await owned(db, Call, call_id, user)
    rows = (
        (await db.execute(select(Job).where(Job.call_id == call.id).order_by(Job.created_at)))
        .scalars()
        .all()
    )
    return {
        "call_id": call.id,
        "version": call.version,
        "processing_status": call.processing_status,
        "analysis_status": call.analysis_status,
        "stages": [
            {
                "id": j.id,
                "stage": j.stage,
                "status": j.status,
                "attempt": j.attempt,
                "reason": j.error_code,
            }
            for j in rows
        ],
        "available_actions": ["manual_transcript"] if call.processing_status == "blocked" else [],
    }


@router.post("/calls/{call_id}/processing/cancel", status_code=202)
async def cancel_processing(
    call_id: str, body: VersionInput, user=Depends(current_user), db=Depends(get_db)
):
    call = await owned(db, Call, call_id, user)
    version_check(call, body.expected_version)
    jobs = (
        (await db.execute(select(Job).where(Job.call_id == call.id).with_for_update()))
        .scalars()
        .all()
    )
    for job in jobs:
        if job.status in ("queued", "running", "retry_wait"):
            job.status = "cancelled"
            job.lease_token = None
    call.processing_status = "cancelled"
    call.version += 1
    return {"call_id": call.id, "version": call.version}


@router.post("/calls/{call_id}/processing/retry", status_code=202)
async def retry_processing(
    call_id: str, body: RetryInput, user=Depends(current_user), db=Depends(get_db)
):
    call = await owned(db, Call, call_id, user)
    version_check(call, body.expected_version)
    jobs = (
        (
            await db.execute(
                select(Job).where(Job.call_id == call.id, Job.stage == body.stage).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if not jobs or jobs[-1].status != "failed":
        raise BusinessError(409, "invalid_transition", "Only failed preparation can retry.")
    job = jobs[-1]
    job.status = "queued"
    job.attempt = 0
    job.not_before = utcnow()
    job.error_code = None
    call.processing_status = "queued"
    call.version += 1
    return {"call_id": call.id, "version": call.version}


@router.delete("/calls/{call_id}", status_code=202)
async def delete_call(
    call_id: str,
    body: VersionInput,
    request: Request,
    user=Depends(current_user),
    db=Depends(get_db),
):
    from mts_backend.processing.retention import erase_call

    call = await owned(db, Call, call_id, user, include_deleted=True)
    if call.deleted_at:
        return {"call_id": call.id, "deletion_status": "completed"}
    version_check(call, body.expected_version)
    await erase_call(db, call, request.app.state.settings)
    await audit(db, user, call, "delete", [])
    return {"call_id": call.id, "deletion_status": "completed"}
