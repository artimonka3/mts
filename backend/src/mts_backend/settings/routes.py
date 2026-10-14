# ruff: noqa: B008 - FastAPI dependency defaults.
import re
from copy import deepcopy
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, utcnow, version_check
from mts_backend.db.models import Agreement, Setting, SettingRevision, User
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["settings"])


class SettingWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=120)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    phrase: str | None = Field(None, min_length=1, max_length=500)
    enabled: bool | None = None
    kind: Literal["commitment", "exclusion"] | None = None
    default_priority: Literal["low", "normal", "high"] | None = None
    default_tags: list[str] | None = Field(None, max_length=30)
    offset_minutes: list[int] | None = Field(None, max_length=10)
    timezone: str | None = Field(None, max_length=80)
    date_only_time: str | None = Field(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_hours: dict | None = None
    expected_version: int | None = Field(None, ge=0)

    @field_validator("name", "phrase")
    @classmethod
    def strip_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Text must not be blank.")
        return value.strip() if value is not None else value

    @field_validator("offset_minutes")
    @classmethod
    def validate_offsets(cls, value):
        if value is not None and any(x < 0 or x > 43200 for x in value):
            raise ValueError("Offsets must be between zero and thirty days.")
        return sorted(set(value)) if value is not None else value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError:
                raise ValueError("Unknown timezone.") from None
        return value

    @field_validator("quiet_hours")
    @classmethod
    def validate_quiet(cls, value):
        if value is not None:
            if set(value) != {"start", "end"}:
                raise ValueError("Quiet hours require start/end hours.")
            if any(type(x) is not int or not 0 <= x <= 23 for x in value.values()):
                raise ValueError("Quiet hours must be whole hours between zero and 23.")
        return value


class DeleteSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class TriggerPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)


ALLOWED = {
    "tag": {"name", "color"},
    "template": {"name", "default_priority", "default_tags", "offset_minutes"},
    "trigger": {"phrase", "enabled", "kind"},
    "reminder_policy": {"enabled", "offset_minutes", "timezone", "quiet_hours", "date_only_time"},
}
DEFAULT_POLICY = {
    "enabled": True,
    "offset_minutes": [60],
    "timezone": "Europe/Minsk",
    "date_only_time": "09:00",
    "quiet_hours": None,
}


def serialize(setting):
    return {"id": setting.id, "version": setting.version, **setting.data}


async def validate_data(db, user, kind, data, exclude_id=None):
    if any(
        value is None and field not in {"color", "quiet_hours"} for field, value in data.items()
    ):
        raise BusinessError(422, "validation_error", "Required setting values cannot be null.")
    if kind in {"tag", "template"} and not data.get("name"):
        raise BusinessError(422, "validation_error", "A name is required.")
    if kind == "trigger" and not data.get("phrase"):
        raise BusinessError(422, "validation_error", "A phrase is required.")
    if kind == "tag":
        rows = await db.scalars(
            select(Setting).where(
                Setting.owner_id == user.id,
                Setting.kind == kind,
                Setting.deleted_at.is_(None),
            )
        )
        if any(
            x.id != exclude_id and x.data["name"].casefold() == data["name"].casefold()
            for x in rows
        ):
            raise BusinessError(409, "duplicate_name", "A tag with this name already exists.")
    for tag_id in data.get("default_tags", []):
        tag = await owned(db, Setting, tag_id, user)
        if tag.kind != "tag":
            raise BusinessError(422, "validation_error", "Default tag must refer to a tag.")


async def save_setting(db, user, kind, body, setting_id=None):
    # Serializes creation/uniqueness and singleton policy updates for this owner.
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    if set(changes) - ALLOWED[kind]:
        raise BusinessError(422, "validation_error", "Fields do not match this setting type.")
    if setting_id:
        item = await owned(db, Setting, setting_id, user)
        if item.kind != kind:
            raise BusinessError(404, "not_found", "Setting not found.")
        if body.expected_version is None:
            raise BusinessError(422, "validation_error", "expected_version is required.")
        version_check(item, body.expected_version)
        data = {**item.data, **changes}
        item.version += 1
    else:
        data = changes
        if kind == "reminder_policy":
            data = {**DEFAULT_POLICY, **data}
        if kind == "trigger":
            data = {"enabled": True, "kind": "commitment", **data}
        if kind == "template":
            data = {"default_priority": "normal", "default_tags": [], **data}
        item = Setting(owner_id=user.id, organization_id=user.organization_id, kind=kind, version=1)
        db.add(item)
    await validate_data(db, user, kind, data, item.id)
    item.data = data
    await db.flush()
    db.add(SettingRevision(setting_id=item.id, version=item.version, data=deepcopy(data)))
    await audit(db, user, item, "setting_saved", list(changes))
    return serialize(item)


async def snapshot_settings(db, user):
    rows = await db.scalars(
        select(Setting)
        .where(
            Setting.owner_id == user.id,
            Setting.organization_id == user.organization_id,
            Setting.deleted_at.is_(None),
        )
        .order_by(Setting.id)
    )
    return {"items": [{"kind": item.kind, **serialize(item)} for item in rows]}


def install_setting_routes(path, kind):
    async def listing(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        rows = list(
            await db.scalars(
                select(Setting)
                .where(
                    Setting.owner_id == user.id,
                    Setting.organization_id == user.organization_id,
                    Setting.kind == kind,
                    Setting.deleted_at.is_(None),
                )
                .order_by(Setting.created_at.desc(), Setting.id.desc())
            )
        )
        return {
            "items": [serialize(x) for x in rows[offset : offset + limit]],
            "total": len(rows),
            "limit": limit,
            "offset": offset,
        }

    async def create(body: SettingWrite, user=Depends(current_user), db=Depends(get_db)):
        return await save_setting(db, user, kind, body)

    async def patch(
        setting_id: str,
        body: SettingWrite,
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        return await save_setting(db, user, kind, body, setting_id)

    async def delete(
        setting_id: str,
        body: DeleteSetting,
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        item = await owned(db, Setting, setting_id, user)
        if item.kind != kind:
            raise BusinessError(404, "not_found", "Setting not found.")
        version_check(item, body.expected_version)
        item.deleted_at = utcnow()
        item.version += 1
        db.add(SettingRevision(setting_id=item.id, version=item.version, data={"deleted": True}))
        if kind == "tag":
            from mts_backend.agreements.service import save_revision
            from mts_backend.tasks.effects import agreement_changed

            agreements = list(
                await db.scalars(
                    select(Agreement)
                    .where(
                        Agreement.owner_id == user.id,
                        Agreement.deleted_at.is_(None),
                    )
                    .with_for_update()
                )
            )
            for agreement in agreements:
                if item.id in agreement.data.get("tag_ids", []):
                    agreement.data = {
                        **agreement.data,
                        "tag_ids": [x for x in agreement.data["tag_ids"] if x != item.id],
                    }
                    agreement.version += 1
                    await save_revision(db, agreement)
                    await agreement_changed(db, agreement, "agreement.tag_removed")
        await audit(db, user, item, "setting_deleted", ["deleted_at"])
        return {"id": item.id, "version": item.version, "deleted": True}

    router.add_api_route(path, listing, methods=["GET"], name=f"list_{kind}")
    router.add_api_route(path, create, methods=["POST"], status_code=201, name=f"create_{kind}")
    router.add_api_route(path + "/{setting_id}", patch, methods=["PATCH"], name=f"patch_{kind}")
    router.add_api_route(path + "/{setting_id}", delete, methods=["DELETE"], name=f"delete_{kind}")


install_setting_routes("/tags", "tag")
install_setting_routes("/task-templates", "template")
install_setting_routes("/trigger-rules", "trigger")


@router.post("/trigger-rules/preview")
async def trigger_preview(body: TriggerPreview, user=Depends(current_user), db=Depends(get_db)):
    rules = await db.scalars(
        select(Setting)
        .where(
            Setting.owner_id == user.id,
            Setting.organization_id == user.organization_id,
            Setting.kind == "trigger",
            Setting.deleted_at.is_(None),
        )
        .order_by(Setting.id)
    )
    matches = []
    for rule in rules:
        if rule.data.get("enabled", True):
            for match in re.finditer(re.escape(rule.data["phrase"]), body.text, re.IGNORECASE):
                matches.append(
                    {
                        "rule_id": rule.id,
                        "version": rule.version,
                        "kind": rule.data.get("kind", "commitment"),
                        "start_cp": match.start(),
                        "end_cp": match.end(),
                    }
                )
    return {"mode": "literal_preview", "semantic_extraction": "not_connected", "matches": matches}


@router.get("/settings/reminders")
async def get_policy(user=Depends(current_user), db=Depends(get_db)):
    item = await db.scalar(
        select(Setting).where(
            Setting.owner_id == user.id,
            Setting.kind == "reminder_policy",
            Setting.deleted_at.is_(None),
        )
    )
    return serialize(item) if item else {"id": None, "version": 0, **DEFAULT_POLICY}


@router.patch("/settings/reminders")
async def patch_policy(body: SettingWrite, user=Depends(current_user), db=Depends(get_db)):
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    item = await db.scalar(
        select(Setting).where(
            Setting.owner_id == user.id,
            Setting.kind == "reminder_policy",
            Setting.deleted_at.is_(None),
        )
    )
    if item is None and body.expected_version not in {None, 0}:
        raise BusinessError(409, "version_conflict", "Initial policy has version zero.")
    return await save_setting(db, user, "reminder_policy", body, item.id if item else None)
