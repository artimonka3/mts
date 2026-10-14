"""Owned transcript read and manual import/edit endpoints."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, utcnow, version_check
from mts_backend.db.models import Call, Transcript
from mts_backend.db.session import get_db
from mts_backend.transcripts.schemas import TranscriptEdit
from mts_backend.transcripts.service import create_revision, serialize_transcript

_DB = Depends(get_db)
_USER = Depends(current_user)

router = APIRouter(prefix="/api/v1", tags=["transcripts"])


@router.get("/calls/{call_id}/transcript")
async def get_transcript(call_id: str, revision_id: UUID | None = None, db=_DB, user=_USER):
    call = await owned(db, Call, call_id, user)
    target = str(revision_id) if revision_id else call.current_transcript_id
    transcript = await db.scalar(
        select(Transcript).where(
            Transcript.id == target,
            Transcript.call_id == call.id,
            Transcript.owner_id == user.id,
            Transcript.organization_id == user.organization_id,
        )
    )
    if not transcript:
        raise BusinessError(404, "not_found", "Transcript not found.")
    return serialize_transcript(transcript, call)


@router.patch("/calls/{call_id}/transcript", status_code=201)
async def patch_transcript(
    call_id: str, body: TranscriptEdit, request: Request, db=_DB, user=_USER
):
    call = await owned(db, Call, call_id, user)
    version_check(call, body.expected_version)
    if body.base_revision_id is not None and body.base_revision_id != call.current_transcript_id:
        raise BusinessError(409, "version_conflict", "The transcript has changed.")
    transcript = await create_revision(db, call, body.segments, mapping=body.speaker_mapping)
    transcript.expires_at = utcnow() + timedelta(
        days=request.app.state.settings.text_retention_days
    )
    await audit(db, user, call, "transcript_edit", ["current_transcript_id"])
    return serialize_transcript(transcript, call)
