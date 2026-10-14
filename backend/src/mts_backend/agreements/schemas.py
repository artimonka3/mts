"""Strict agreement fields, deadlines and source spans."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DueBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: str = "Europe/Minsk"
    original_text: str | None = Field(default=None, max_length=2000)
    basis_call_at: datetime | None = None
    normalization_source: Literal["manual", "fixture", "model"] = "manual"
    ambiguous: bool = False
    ambiguity_reasons: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def check_zone(self):
        try:
            zone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone.") from exc
        for name in ("basis_call_at", "at", "start", "end"):
            value = getattr(self, name, None)
            if value is not None:
                if value.tzinfo is None:
                    raise ValueError("Timestamp must include timezone.")
                if value.utcoffset() != value.astimezone(zone).utcoffset():
                    raise ValueError("Timestamp offset and timezone disagree.")
        return self


class DateDue(DueBase):
    kind: Literal["date_only"]
    date: date


class InstantDue(DueBase):
    kind: Literal["instant"]
    at: datetime


class IntervalDue(DueBase):
    kind: Literal["interval"]
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def order(self):
        if self.end < self.start:
            raise ValueError("Invalid interval.")
        return self


class UnknownDue(DueBase):
    kind: Literal["unknown"] = "unknown"


Due = Annotated[DateDue | InstantDue | IntervalDue | UnknownDue, Field(discriminator="kind")]


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript_revision_id: str
    segment_id: str
    start_cp: int = Field(ge=0)
    end_cp: int = Field(ge=0)
    quote: str = Field(max_length=20000)

    @field_validator("transcript_revision_id")
    @classmethod
    def uuid_reference(cls, value):
        return str(UUID(value))


class AgreementCreate(BaseModel):
    @field_validator("obligor_participant_id", "recipient_participant_id")
    @classmethod
    def uuid_reference(cls, value):
        return str(UUID(value)) if value else None

    @field_validator("tag_ids")
    @classmethod
    def uuid_tags(cls, values):
        return [str(UUID(v)) for v in values] if values is not None else None

    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1, max_length=2000)
    obligor_participant_id: str | None = None
    recipient_participant_id: str | None = None
    due: Due = Field(default_factory=UnknownDue)
    condition: str | None = Field(default=None, max_length=2000)
    needs_details: list[str] = Field(default_factory=list, max_length=30)
    priority: Literal["low", "normal", "high"] = "normal"
    tag_ids: list[str] = Field(default_factory=list, max_length=100)
    manual_confidence_override: float | None = Field(default=None, ge=0, le=1)
    evidence: list[EvidenceInput] = Field(default_factory=list, max_length=100)


class AgreementEdit(BaseModel):
    @field_validator("obligor_participant_id", "recipient_participant_id")
    @classmethod
    def uuid_reference(cls, value):
        return str(UUID(value)) if value else None

    @field_validator("tag_ids")
    @classmethod
    def uuid_tags(cls, values):
        return [str(UUID(v)) for v in values] if values is not None else None

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    confirm_changes: bool = False
    action: str | None = Field(default=None, min_length=1, max_length=2000)
    obligor_participant_id: str | None = None
    recipient_participant_id: str | None = None
    due: Due | None = None
    condition: str | None = Field(default=None, max_length=2000)
    needs_details: list[str] | None = Field(default=None, max_length=30)
    priority: Literal["low", "normal", "high"] | None = None
    tag_ids: list[str] | None = Field(default=None, max_length=100)
    manual_confidence_override: float | None = Field(default=None, ge=0, le=1)
    evidence: list[EvidenceInput] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def reject_null(self):
        required = {"action", "due", "needs_details", "priority", "tag_ids", "evidence"}
        if any(getattr(self, key) is None for key in required & self.model_fields_set):
            raise ValueError("Required agreement fields cannot be null.")
        return self


class AgreementTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    condition_resolution: str | None = Field(default=None, min_length=1, max_length=2000)
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
