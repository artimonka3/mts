"""Fixture-only analysis, editable summary and assembled result."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from mts_backend.agreements.service import serialize_agreement
from mts_backend.analysis.fixtures import fixture_matches, get_scenario, load_dataset, provenance
from mts_backend.analysis.service import next_summary_version, run_fixture, serialize_summary
from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, uid, utcnow, version_check
from mts_backend.db.models import Agreement, Call, Summary, Transcript
from mts_backend.db.session import get_db

_DB = Depends(get_db)
_USER = Depends(current_user)

router = APIRouter(prefix="/api/v1", tags=["analysis"])


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    transcript_revision_id: str
    settings_version: int | None = Field(default=None, ge=1)

    @field_validator("transcript_revision_id")
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value))


class SummaryEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    summary: str | None = Field(default=None, max_length=20000)
    client_message_draft: str | None = Field(default=None, max_length=20000)


@router.get("/demo/scenarios")
async def list_scenarios(request: Request, user=_USER):
    dataset = load_dataset(request.app.state.settings.fixture_path)
    return {
        "items": [
            {"id": d["id"], "title": d["title"], "call_at": d["call_at"], "timezone": d["timezone"]}
            for d in dataset["dialogues"]
        ],
        "provenance": provenance(),
    }


@router.get("/calls/{call_id}/result")
async def result(call_id: str, db=_DB, user=_USER):
    call = await owned(db, Call, call_id, user)
    summary = await db.get(Summary, call.current_summary_id) if call.current_summary_id else None
    agreements = (
        await db.scalars(
            select(Agreement)
            .where(
                Agreement.call_id == call.id,
                Agreement.owner_id == user.id,
                Agreement.organization_id == user.organization_id,
                Agreement.deleted_at.is_(None),
            )
            .order_by(Agreement.created_at, Agreement.id)
        )
    ).all()
    return {
        "call_id": call.id,
        "call_version": call.version,
        "transcript_revision_id": call.current_transcript_id,
        "analysis_status": call.analysis_status,
        "summary": serialize_summary(summary),
        "agreements": [await serialize_agreement(db, a) for a in agreements],
        "provenance": provenance() if call.is_demo else {"source": "manual", "is_demo": False},
        "capabilities": {
            "llm": "disabled",
            "asr": "disabled",
            "diarization": "disabled",
            "fixture_analysis": call.is_demo,
            "manual_edit": True,
        },
    }


@router.post("/calls/{call_id}/analysis", status_code=202)
async def analyze(
    call_id: str,
    body: AnalysisRequest,
    request: Request,
    db=_DB,
    user=_USER,
):
    call = await owned(db, Call, call_id, user)
    version_check(call, body.expected_version)
    transcript = await db.scalar(
        select(Transcript).where(
            Transcript.id == body.transcript_revision_id,
            Transcript.call_id == call.id,
            Transcript.owner_id == user.id,
            Transcript.organization_id == user.organization_id,
        )
    )
    if not transcript:
        raise BusinessError(404, "not_found", "Transcript not found.")
    if transcript.availability != "available":
        raise BusinessError(410, "source_expired", "Transcript is unavailable.")
    if transcript.id != call.current_transcript_id:
        raise BusinessError(409, "version_conflict", "Analyze the current transcript revision.")
    if not call.is_demo:
        raise BusinessError(
            503, "provider_unavailable", "LLM analysis is not connected; use manual editing."
        )
    scenario = get_scenario(call.scenario_id, request.app.state.settings.fixture_path)
    if not fixture_matches(call, transcript, scenario):
        raise BusinessError(
            503,
            "provider_unavailable",
            "Only unchanged allowlisted demo text has a fixture result.",
        )
    from mts_backend.settings.routes import snapshot_settings

    snapshot = await snapshot_settings(db, user)
    run = await run_fixture(
        db, call, transcript, scenario, snapshot, request.app.state.settings.text_retention_days
    )
    await audit(db, user, call, "fixture_analysis", ["analysis_status"])
    return {
        "analysis_run_id": run.id,
        "status": "ready",
        "call_version": call.version,
        "provenance": provenance(),
    }


@router.patch("/calls/{call_id}/summary")
async def edit_summary(
    call_id: str,
    body: SummaryEdit,
    request: Request,
    db=_DB,
    user=_USER,
):
    call = await owned(db, Call, call_id, user)
    current = await db.get(Summary, call.current_summary_id) if call.current_summary_id else None
    if current is None:
        if body.expected_version != 1:
            raise BusinessError(
                409, "version_conflict", "Use version 1 to create a first manual summary."
            )
    else:
        version_check(current, body.expected_version)
        if current.availability != "available":
            raise BusinessError(410, "source_expired", "Summary source is unavailable.")
    summary = Summary(
        id=uid(),
        call_id=call.id,
        owner_id=user.id,
        organization_id=user.organization_id,
        version=await next_summary_version(db, call),
        summary=body.summary if body.summary is not None else (current.summary if current else ""),
        client_message_draft=body.client_message_draft
        if body.client_message_draft is not None
        else (current.client_message_draft if current else ""),
        source="manual",
        expires_at=utcnow() + timedelta(days=request.app.state.settings.text_retention_days),
        availability="available",
    )
    db.add(summary)
    await db.flush()
    call.current_summary_id = summary.id
    call.version += 1
    await audit(db, user, call, "summary_edit", list(body.model_fields_set - {"expected_version"}))
    return {**serialize_summary(summary), "call_version": call.version}
