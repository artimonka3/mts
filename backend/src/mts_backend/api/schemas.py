"""Technical responses and explicit MVP capabilities."""

from typing import Literal

from pydantic import BaseModel, Field


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"
    database: Literal["ok"] = "ok"
    schema_revision: Literal["0003_encrypted_metadata"] = Field(
        default="0003_encrypted_metadata", alias="schema"
    )


class DisabledProcessing(BaseModel):
    asr: Literal["disabled"] = "disabled"
    diarization: Literal["disabled"] = "disabled"
    llm: Literal["disabled"] = "disabled"


class CapabilitiesResponse(BaseModel):
    stage: Literal[13] = 13
    processing: DisabledProcessing
    business_api: Literal["mvp"] = "mvp"
    analysis_modes: list[str] = Field(default_factory=lambda: ["known_demo", "manual"])
    accuracy: Literal["not_measured"] = "not_measured"
