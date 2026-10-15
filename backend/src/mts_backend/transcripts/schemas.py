"""Validated manual transcript revisions; no transcription model is used."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SegmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    position: int = Field(ge=0)
    speaker_id: str | None = Field(default=None, max_length=100)
    participant_id: str | None = None
    text: str = Field(max_length=20000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_times(self):
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("Both timestamps must be supplied together.")
        if self.start_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("The end must not precede the start.")
        return self


class TranscriptEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    base_revision_id: str | None = None
    segments: list[SegmentInput] = Field(max_length=10000)
    speaker_mapping: dict[str, str | None] | None = None
