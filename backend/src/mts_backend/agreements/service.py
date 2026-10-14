"""Revisioned agreement data and exact Unicode evidence verification."""

from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from mts_backend.core.business import BusinessError, uid, utcnow
from mts_backend.db.models import AgreementRevision, Call, Participant, Setting, Transcript


def validate_span(segment, evidence):
    start, end = evidence["start_cp"], evidence["end_cp"]
    text = segment["text"]
    if not 0 <= start < end <= len(text) or text[start:end] != evidence["quote"]:
        raise BusinessError(422, "invalid_evidence", "Evidence does not match the source span.")
    return {
        **evidence,
        "availability": "available",
        "start_ms": segment.get("start_ms"),
        "end_ms": segment.get("end_ms"),
    }


async def validate_agreement_data(db, call, data):
    result = deepcopy(data)
    if not result.get("action", "").strip():
        raise BusinessError(422, "invalid_action", "Action must not be empty.")
    for field in ("obligor_participant_id", "recipient_participant_id"):
        reference = result.get(field)
        if reference:
            found = await db.scalar(
                select(Participant.id).where(
                    Participant.id == reference,
                    Participant.call_id == call.id,
                    Participant.owner_id == call.owner_id,
                    Participant.organization_id == call.organization_id,
                )
            )
            if not found:
                raise BusinessError(
                    422, "invalid_participant", "Participant does not belong to this call."
                )
    for reference in result.get("tag_ids", []):
        found = await db.scalar(
            select(Setting.id).where(
                Setting.id == reference,
                Setting.owner_id == call.owner_id,
                Setting.organization_id == call.organization_id,
                Setting.kind == "tag",
                Setting.deleted_at.is_(None),
            )
        )
        if not found:
            raise BusinessError(422, "invalid_tag", "Tag is unavailable.")
    checked = []
    for evidence in result.get("evidence", []):
        transcript = await db.scalar(
            select(Transcript).where(
                Transcript.id == evidence["transcript_revision_id"],
                Transcript.call_id == call.id,
                Transcript.owner_id == call.owner_id,
                Transcript.organization_id == call.organization_id,
            )
        )
        if not transcript:
            raise BusinessError(
                422, "invalid_evidence", "Evidence transcript does not belong to this call."
            )
        if transcript.availability != "available":
            if "quote" not in evidence and evidence.get("availability") in {"expired", "deleted"}:
                checked.append({**evidence, "availability": transcript.availability})
                continue
            raise BusinessError(410, "source_expired", "Evidence source is unavailable.")
        segment = next((s for s in transcript.segments if s["id"] == evidence["segment_id"]), None)
        if segment is None:
            raise BusinessError(422, "invalid_evidence", "Evidence segment is unavailable.")
        checked.append(validate_span(segment, evidence))
    result["evidence"] = checked
    due = result["due"]
    needs = list(dict.fromkeys(result.get("needs_details", [])))
    if (due["kind"] == "unknown" or due.get("ambiguous")) and "due" not in needs:
        needs.append("due")
    if due["kind"] != "unknown" and not due.get("ambiguous") and "due" in needs:
        needs.remove("due")
    if (
        result.get("condition")
        and not result.get("condition_resolution")
        and "condition" not in needs
    ):
        needs.append("condition")
    if not result.get("obligor_participant_id") and "obligor_identity" not in needs:
        needs.append("obligor_identity")
    result["needs_details"] = needs
    return result


def agreement_snapshot(agreement):
    return {
        "verification": agreement.verification,
        "execution": agreement.execution,
        "source": agreement.source,
        "accepted_at": agreement.accepted_at.isoformat() if agreement.accepted_at else None,
        "data": deepcopy(agreement.data),
    }


async def save_revision(db, agreement):
    db.add(
        AgreementRevision(
            id=uid(),
            agreement_id=agreement.id,
            version=agreement.version,
            data=agreement_snapshot(agreement),
            created_at=utcnow(),
        )
    )
    await db.flush()


def due_overdue(due, now=None):
    now = now or utcnow()
    if due["kind"] == "unknown":
        return False
    if due["kind"] == "date_only":
        return date.fromisoformat(due["date"]) < now.astimezone(ZoneInfo(due["timezone"])).date()
    target = due.get("at") or due.get("end")
    return datetime.fromisoformat(target) < now


async def evidence_response(db, agreement):
    evidence = deepcopy(agreement.data.get("evidence", []))
    for item in evidence:
        transcript = await db.get(Transcript, item["transcript_revision_id"])
        availability = transcript.availability if transcript else "deleted"
        item["availability"] = availability
        if availability != "available":
            item.pop("quote", None)
            item.pop("context", None)
    return evidence


async def serialize_agreement(db, agreement):
    call = await db.get(Call, agreement.call_id)
    data = deepcopy(agreement.data)
    data["evidence"] = await evidence_response(db, agreement)
    requires_recheck = bool(
        agreement.transcript_id and agreement.transcript_id != call.current_transcript_id
    )
    requires_recheck |= any(
        e["transcript_revision_id"] != call.current_transcript_id for e in data["evidence"]
    )
    return {
        "id": agreement.id,
        "call_id": agreement.call_id,
        "version": agreement.version,
        **data,
        "verification": agreement.verification,
        "execution": agreement.execution,
        "accepted_at": agreement.accepted_at.isoformat() if agreement.accepted_at else None,
        "overdue": agreement.verification == "accepted"
        and agreement.execution in {"open", "in_progress"}
        and due_overdue(data["due"]),
        "requires_recheck": bool(requires_recheck),
        "provenance": {"source": agreement.source, "is_demo": call.is_demo},
    }
