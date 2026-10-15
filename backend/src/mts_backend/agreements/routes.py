"""Owned, versioned proposal review and evidence API."""

import hashlib
import json
import re
from copy import deepcopy
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from mts_backend.agreements.schemas import AgreementCreate, AgreementEdit, AgreementTransition
from mts_backend.agreements.service import (
    evidence_response,
    save_revision,
    serialize_agreement,
    validate_agreement_data,
)
from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, uid, utcnow, version_check
from mts_backend.db.models import Agreement, AgreementRevision, Call, IdempotencyRecord, Transcript
from mts_backend.db.session import get_db

_DB = Depends(get_db)
_USER = Depends(current_user)

router = APIRouter(prefix="/api/v1", tags=["agreements"])


async def agreement_call(db, agreement, user):
    return await owned(db, Call, agreement.call_id, user)


@router.get("/calls/{call_id}/agreements")
async def list_agreements(
    call_id: str,
    verification: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=_DB,
    user=_USER,
):
    call = await owned(db, Call, call_id, user)
    query = select(Agreement).where(
        Agreement.call_id == call.id,
        Agreement.owner_id == user.id,
        Agreement.organization_id == user.organization_id,
        Agreement.deleted_at.is_(None),
    )
    if verification:
        if verification not in {"proposed", "accepted", "rejected"}:
            raise BusinessError(422, "invalid_filter", "Unknown verification state.")
        query = query.where(Agreement.verification == verification)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    items = (
        await db.scalars(
            query.order_by(Agreement.created_at.desc(), Agreement.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [await serialize_agreement(db, item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/calls/{call_id}/agreements", status_code=201)
async def create_agreement(call_id: str, body: AgreementCreate, db=_DB, user=_USER):
    call = await owned(db, Call, call_id, user)
    data = body.model_dump(mode="json")
    data["due"]["basis_call_at"] = (
        data["due"].get("basis_call_at")
        or call.call_at.astimezone(ZoneInfo(data["due"]["timezone"])).isoformat()
    )
    data["confidence"] = {"value": None, "source": "unknown", "calibration": None}
    data = await validate_agreement_data(db, call, data)
    agreement = Agreement(
        id=uid(),
        call_id=call.id,
        owner_id=user.id,
        organization_id=user.organization_id,
        version=1,
        source="manual",
        data=data,
        verification="proposed",
        execution="open",
        transcript_id=data["evidence"][0]["transcript_revision_id"] if data["evidence"] else None,
    )
    db.add(agreement)
    await db.flush()
    await save_revision(db, agreement)
    await audit(db, user, agreement, "create", ["action", "due", "evidence"])
    return await serialize_agreement(db, agreement)


@router.get("/agreements/{agreement_id}")
async def get_agreement(agreement_id: str, db=_DB, user=_USER):
    agreement = await owned(db, Agreement, agreement_id, user)
    await agreement_call(db, agreement, user)
    return await serialize_agreement(db, agreement)


@router.patch("/agreements/{agreement_id}")
async def edit_agreement(agreement_id: str, body: AgreementEdit, db=_DB, user=_USER):
    agreement = await owned(db, Agreement, agreement_id, user)
    call = await agreement_call(db, agreement, user)
    version_check(agreement, body.expected_version)
    if agreement.verification == "accepted" and not body.confirm_changes:
        raise BusinessError(409, "confirmation_required", "Confirm edits to an accepted agreement.")
    changes = body.model_dump(
        mode="json", exclude_unset=True, exclude={"expected_version", "confirm_changes"}
    )
    data = deepcopy(agreement.data)
    data.update(changes)
    if "due" in changes:
        data["due"]["normalization_source"] = "manual"
        data["due"]["basis_call_at"] = (
            data["due"].get("basis_call_at")
            or call.call_at.astimezone(ZoneInfo(data["due"]["timezone"])).isoformat()
        )
    if "condition" in changes:
        data.pop("condition_resolution", None)
        data["needs_details"] = [d for d in data.get("needs_details", []) if d != "condition"]
    agreement.data = await validate_agreement_data(db, call, data)
    if agreement.verification != "accepted":
        agreement.verification = "proposed"
    agreement.version += 1
    await save_revision(db, agreement)
    from mts_backend.tasks.effects import agreement_changed

    await agreement_changed(db, agreement, "agreement.updated")
    await audit(db, user, agreement, "edit", list(changes))
    return await serialize_agreement(db, agreement)


async def transition(agreement_id, action, body, key, db, user):
    agreement = await owned(db, Agreement, agreement_id, user)
    await agreement_call(db, agreement, user)
    if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise BusinessError(400, "invalid_idempotency_key", "Idempotency-Key is required.")
    operation = f"agreements:{agreement_id}:{action}"
    digest = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    existing = await db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.owner_id == user.id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    if existing:
        if existing.digest != digest:
            raise BusinessError(
                409, "idempotency_conflict", "The key was used with another request."
            )
        # Return the original snapshot; retention still redacts any expired quotes.
        replay = deepcopy(existing.response)
        for evidence in replay.get("evidence", []):
            transcript = await db.get(Transcript, evidence["transcript_revision_id"])
            if transcript is None or transcript.availability != "available":
                evidence.pop("quote", None)
                evidence["availability"] = transcript.availability if transcript else "deleted"
        return replay
    version_check(agreement, body.expected_version)
    allowed = {
        "accept": {"proposed"},
        "reject": {"proposed", "accepted"},
        "unconfirm": {"accepted"},
    }
    if agreement.verification not in allowed[action]:
        raise BusinessError(409, "invalid_transition", "This review transition is not allowed.")
    if action == "accept":
        if agreement.data.get("condition") and not body.condition_resolution:
            raise BusinessError(
                409, "condition_unresolved", "Confirm the condition before acceptance."
            )
        if body.condition_resolution:
            data = deepcopy(agreement.data)
            data["condition_resolution"] = body.condition_resolution
            data["needs_details"] = [d for d in data.get("needs_details", []) if d != "condition"]
            agreement.data = data
        agreement.verification = "accepted"
        agreement.execution = "open"
        agreement.accepted_at = utcnow()
    elif action == "reject":
        agreement.verification = "rejected"
    else:
        if not body.reason:
            raise BusinessError(
                422, "reason_required", "Specify the reason for removing confirmation."
            )
        agreement.verification = "proposed"
    agreement.version += 1
    await save_revision(db, agreement)
    from mts_backend.tasks.effects import agreement_changed

    await agreement_changed(db, agreement, f"agreement.{action}")
    await audit(db, user, agreement, action, ["verification"])
    response = await serialize_agreement(db, agreement)
    db.add(
        IdempotencyRecord(
            id=uid(),
            owner_id=user.id,
            operation=operation,
            key=key,
            digest=digest,
            response=response,
            status_code=200,
        )
    )
    return response


@router.post("/agreements/{agreement_id}/accept")
async def accept(
    agreement_id: str,
    body: AgreementTransition,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    db=_DB,
    user=_USER,
):
    return await transition(agreement_id, "accept", body, key, db, user)


@router.post("/agreements/{agreement_id}/reject")
async def reject(
    agreement_id: str,
    body: AgreementTransition,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    db=_DB,
    user=_USER,
):
    return await transition(agreement_id, "reject", body, key, db, user)


@router.post("/agreements/{agreement_id}/unconfirm")
async def unconfirm(
    agreement_id: str,
    body: AgreementTransition,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    db=_DB,
    user=_USER,
):
    return await transition(agreement_id, "unconfirm", body, key, db, user)


@router.get("/agreements/{agreement_id}/evidence")
async def get_evidence(agreement_id: str, db=_DB, user=_USER):
    agreement = await owned(db, Agreement, agreement_id, user)
    await agreement_call(db, agreement, user)
    return {"agreement_id": agreement.id, "items": await evidence_response(db, agreement)}


@router.get("/agreements/{agreement_id}/history")
async def get_history(agreement_id: str, db=_DB, user=_USER):
    agreement = await owned(db, Agreement, agreement_id, user)
    await agreement_call(db, agreement, user)
    revisions = (
        await db.scalars(
            select(AgreementRevision)
            .where(AgreementRevision.agreement_id == agreement.id)
            .order_by(AgreementRevision.version)
        )
    ).all()
    items = []
    for revision in revisions:
        snapshot = deepcopy(revision.data)
        for evidence in snapshot.get("data", {}).get("evidence", []):
            transcript = await db.get(Transcript, evidence["transcript_revision_id"])
            if transcript is None or transcript.availability != "available":
                evidence.pop("quote", None)
                evidence["availability"] = transcript.availability if transcript else "deleted"
        items.append(
            {"version": revision.version, "created_at": revision.created_at.isoformat(), **snapshot}
        )
    return {"agreement_id": agreement.id, "items": items}


class DueNormalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phrase: str = Field(min_length=1, max_length=2000)


@router.post("/calls/{call_id}/due/normalize")
async def normalize_deadline(call_id: str, body: DueNormalizeRequest, db=_DB, user=_USER):
    from mts_backend.agreements.dates import normalize_due

    call = await owned(db, Call, call_id, user)
    return normalize_due(call, body.phrase)
