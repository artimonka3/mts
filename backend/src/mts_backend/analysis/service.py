"""Fixture result initialization and immutable analysis/summary revisions."""

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

from mts_backend.agreements.service import save_revision, validate_agreement_data
from mts_backend.analysis.fixtures import get_scenario
from mts_backend.core.business import uid, utcnow
from mts_backend.db.models import Agreement, AnalysisRun, Notification, Participant, Summary
from mts_backend.transcripts.service import create_revision


def serialize_summary(summary):
    if summary is None:
        return None
    return {
        "id": summary.id,
        "version": summary.version,
        "summary": summary.summary if summary.availability == "available" else None,
        "client_message_draft": summary.client_message_draft
        if summary.availability == "available"
        else None,
        "source": summary.source,
        "availability": summary.availability,
    }


async def next_summary_version(db, call):
    latest = await db.scalar(
        select(Summary.version)
        .where(Summary.call_id == call.id)
        .order_by(Summary.version.desc())
        .limit(1)
    )
    return (latest or 0) + 1


async def initialize_demo(db, call, scenario, retention_days=30):
    if isinstance(scenario, str):
        scenario = get_scenario(scenario)
    mapping = {}
    for participant in scenario["participants"]:
        item = Participant(
            id=uid(),
            call_id=call.id,
            owner_id=call.owner_id,
            organization_id=call.organization_id,
            display_name=participant.get("display_name"),
            role=participant.get("role", "unknown"),
            speaker_id=participant["id"],
        )
        db.add(item)
        mapping[participant["id"]] = item.id
    await db.flush()
    segments = []
    for segment in scenario["segments"]:
        item = deepcopy(segment)
        item["id"] = uid()
        item["participant_id"] = mapping.get(item.get("participant_id"))
        segments.append(item)
    transcript = await create_revision(db, call, segments, source="fixture")
    transcript.expires_at = utcnow() + timedelta(days=retention_days)
    from mts_backend.settings.routes import snapshot_settings

    snapshot = await snapshot_settings(
        db, SimpleNamespace(id=call.owner_id, organization_id=call.organization_id)
    )
    run = await run_fixture(db, call, transcript, scenario, snapshot, retention_days)
    return run


async def run_fixture(db, call, transcript, scenario, settings_snapshot, retention_days=30):
    run = AnalysisRun(
        id=uid(),
        call_id=call.id,
        owner_id=call.owner_id,
        organization_id=call.organization_id,
        transcript_id=transcript.id,
        status="ready",
        source="fixture",
        settings_snapshot=deepcopy(settings_snapshot),
    )
    db.add(run)
    await db.flush()
    segment_map = {
        original["id"]: current
        for original, current in zip(scenario["segments"], transcript.segments, strict=True)
    }
    participant_map = {
        participant.speaker_id: participant.id
        for participant in await db.scalars(
            select(Participant).where(Participant.call_id == call.id)
        )
        if participant.speaker_id
    }
    participant_map.update(
        {
            segment.get("speaker_id"): segment.get("participant_id")
            for segment in transcript.segments
            if segment.get("speaker_id")
        }
    )
    actions = []
    for expected in scenario["gold"]["agreements"]:
        data = {
            k: deepcopy(expected.get(k))
            for k in (
                "action",
                "obligor_participant_id",
                "recipient_participant_id",
                "due",
                "condition",
                "needs_details",
            )
        }
        for field in ("obligor_participant_id", "recipient_participant_id"):
            data[field] = participant_map.get(data[field])
        data["priority"] = "normal"
        data["tag_ids"] = []
        data["confidence"] = {"value": None, "source": "fixture", "calibration": None}
        data["manual_confidence_override"] = None
        data["evidence"] = [
            {
                "transcript_revision_id": transcript.id,
                "segment_id": segment_map[e["segment_id"]]["id"],
                "start_cp": e["start_cp"],
                "end_cp": e["end_cp"],
                "quote": e["quote"],
            }
            for e in expected["evidence"]
        ]
        data = await validate_agreement_data(db, call, data)
        agreement = Agreement(
            id=uid(),
            call_id=call.id,
            owner_id=call.owner_id,
            organization_id=call.organization_id,
            analysis_run_id=run.id,
            transcript_id=transcript.id,
            source="fixture",
            version=1,
            verification="proposed",
            execution="open",
            data=data,
        )
        db.add(agreement)
        await db.flush()
        await save_revision(db, agreement)
        db.add(
            Notification(
                id=uid(),
                owner_id=call.owner_id,
                organization_id=call.organization_id,
                agreement_id=agreement.id,
                kind="confirmation",
                version=1,
                deduplication_key=f"confirmation:{agreement.id}:1",
            )
        )
        actions.append(data["action"])
    # Reruns create proposals, and preserve a user-edited summary as current.
    current = await db.get(Summary, call.current_summary_id) if call.current_summary_id else None
    if current is None or current.source != "manual":
        text = (
            "Обсудили: " + "; ".join(actions)
            if actions
            else "Явных договорённостей не зафиксировано."
        )
        summary = Summary(
            id=uid(),
            call_id=call.id,
            owner_id=call.owner_id,
            organization_id=call.organization_id,
            analysis_run_id=run.id,
            version=await next_summary_version(db, call),
            summary=text,
            client_message_draft="Спасибо за разговор. " + text,
            source="fixture",
            availability="available",
            expires_at=utcnow() + timedelta(days=retention_days),
        )
        db.add(summary)
        await db.flush()
        call.current_summary_id = summary.id
    call.analysis_status = "ready"
    call.version += 1
    return run
