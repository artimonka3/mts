from datetime import UTC, datetime

import pytest

from mts_backend.analysis.provider import (
    AnalysisInput,
    AnalysisUnavailable,
    DisabledAnalysisProvider,
)


async def test_disabled_provider_explicitly_refuses_analysis():
    source = AnalysisInput(
        transcript_version_id="version-1",
        transcript_text="private transcript text",
        call_started_at=datetime(2026, 10, 14, tzinfo=UTC),
        timezone="Europe/Minsk",
    )
    with pytest.raises(AnalysisUnavailable, match="LLM analysis is not connected") as raised:
        await DisabledAnalysisProvider().analyze(source)
    assert "private transcript text" not in str(raised.value)
