"""A disabled analysis boundary; this scaffold does not perform inference."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    transcript_version_id: str
    transcript_text: str
    call_started_at: datetime
    timezone: str


class AnalysisUnavailable(RuntimeError):
    """No analysis provider has been connected."""


class AnalysisProvider(Protocol):
    async def analyze(self, source: AnalysisInput) -> object:
        """Return a future validated analysis result or raise AnalysisUnavailable."""
        ...


class DisabledAnalysisProvider:
    async def analyze(self, source: AnalysisInput) -> object:
        raise AnalysisUnavailable("LLM analysis is not connected.")
