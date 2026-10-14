"""Append-only transcript editing and speaker assignment."""

from sqlalchemy import select

from mts_backend.core.business import BusinessError, uid, utcnow
from mts_backend.db.models import Participant, Transcript


def serialize_transcript(transcript, call):
    if transcript.availability != "available":
        raise BusinessError(410, "source_expired", "Transcript source is unavailable.")
    return {
        "id": transcript.id,
        "call_id": call.id,
        "revision": transcript.revision,
        "source": transcript.source,
        "is_demo": call.is_demo,
        "availability": transcript.availability,
        "segments": transcript.segments,
        "call_version": call.version,
        "created_at": transcript.created_at.isoformat(),
    }


async def create_revision(db, call, segments, source="manual", mapping=None):
    participants = {
        p.id: p
        for p in (
            await db.scalars(
                select(Participant).where(
                    Participant.call_id == call.id,
                    Participant.owner_id == call.owner_id,
                    Participant.organization_id == call.organization_id,
                )
            )
        ).all()
    }
    mapping = mapping or {}
    if any(p and p not in participants for p in mapping.values()):
        raise BusinessError(422, "invalid_participant", "Participant does not belong to this call.")
    positions, ids = set(), set()
    normalized = []
    for incoming in segments:
        data = incoming.model_dump() if hasattr(incoming, "model_dump") else dict(incoming)
        data["id"] = data.get("id") or uid()
        data["participant_id"] = mapping.get(data.get("speaker_id"), data.get("participant_id"))
        if data.get("participant_id") and data["participant_id"] not in participants:
            raise BusinessError(
                422, "invalid_participant", "Participant does not belong to this call."
            )
        if data["position"] in positions or data["id"] in ids:
            raise BusinessError(
                422, "duplicate_segment", "Segment IDs and positions must be unique."
            )
        positions.add(data["position"])
        ids.add(data["id"])
        normalized.append(data)
    normalized.sort(key=lambda item: item["position"])
    latest = await db.scalar(
        select(Transcript.revision)
        .where(Transcript.call_id == call.id)
        .order_by(Transcript.revision.desc())
        .limit(1)
    )
    revision = Transcript(
        id=uid(),
        call_id=call.id,
        owner_id=call.owner_id,
        organization_id=call.organization_id,
        revision=(latest or 0) + 1,
        source=source,
        segments=normalized,
        availability="available",
        created_at=utcnow(),
    )
    db.add(revision)
    await db.flush()
    call.current_transcript_id = revision.id
    call.processing_status = "transcript_ready"
    call.analysis_status = "not_connected"
    call.version += 1
    return revision
