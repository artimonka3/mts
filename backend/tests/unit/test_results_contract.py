"""Small regression checks for manual results and synthetic-only processing."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mts_backend.agreements.schemas import AgreementCreate, AgreementEdit, DateDue, UnknownDue
from mts_backend.agreements.service import due_overdue, validate_span
from mts_backend.analysis.fixtures import fixture_matches, get_scenario
from mts_backend.core.business import BusinessError
from mts_backend.transcripts.schemas import SegmentInput


def test_evidence_uses_codepoints_not_bytes_or_utf16():
    span = {"start_cp": 1, "end_cp": 2, "quote": "🌲"}
    assert validate_span({"text": "А🌲Б", "start_ms": None, "end_ms": None}, span)["quote"] == "🌲"
    with pytest.raises(BusinessError) as exc:
        validate_span({"text": "А🌲Б"}, {**span, "end_cp": 3})
    assert exc.value.code == "invalid_evidence"


@pytest.mark.parametrize("fields", [{"date": "2026-10-17"}, {"at": None}, {"end": None}])
def test_unknown_due_rejects_fabricated_date_fields(fields):
    with pytest.raises(ValidationError):
        UnknownDue(**fields)


def test_deadline_offset_must_match_timezone():
    with pytest.raises(ValidationError):
        AgreementCreate(
            action="Звонок",
            due={"kind": "instant", "timezone": "Europe/Minsk", "at": "2026-10-17T11:00:00+00:00"},
        )


def test_date_only_overdue_boundary_uses_local_date():
    due = DateDue(kind="date_only", date="2026-10-17").model_dump(mode="json")
    assert not due_overdue(due, datetime(2026, 10, 17, 20, 59, tzinfo=UTC))
    assert due_overdue(due, datetime(2026, 10, 17, 21, 0, tzinfo=UTC))


def test_segments_require_timestamp_pair_and_order():
    with pytest.raises(ValidationError):
        SegmentInput(position=0, text="a", start_ms=1)
    with pytest.raises(ValidationError):
        SegmentInput(position=0, text="a", start_ms=2, end_ms=1)
    assert SegmentInput(position=0, text="").start_ms is None


def test_empty_or_null_required_edit_fields_rejected():
    with pytest.raises(ValidationError):
        AgreementEdit(expected_version=1, due=None)
    with pytest.raises(ValidationError):
        AgreementCreate(action="")


def test_fixture_requires_exact_text_and_demo_provenance():
    fixture = get_scenario("syn_01")
    call = SimpleNamespace(
        is_demo=True,
        scenario_id="syn_01",
        timezone="Europe/Minsk",
        call_at=datetime.fromisoformat(fixture["call_at"]),
    )
    transcript = SimpleNamespace(segments=fixture["segments"])
    assert fixture_matches(call, transcript, fixture)
    call.is_demo = False
    assert not fixture_matches(call, transcript, fixture)
    call.is_demo = True
    transcript.segments = [{**s, "text": "Изменённый текст"} for s in fixture["segments"]]
    assert not fixture_matches(call, transcript, fixture)


def test_relative_dates_use_local_call_date_across_year_boundary():
    from mts_backend.agreements.dates import normalize_due

    call = SimpleNamespace(
        timezone="Europe/Minsk", call_at=datetime.fromisoformat("2026-12-31T23:30:00+03:00")
    )
    tomorrow = normalize_due(call, "завтра")
    assert tomorrow["date"] == "2027-01-01" and tomorrow["normalization_source"] == "manual"
    assert normalize_due(call, "через 3 дня")["date"] == "2027-01-03"
    assert tomorrow["basis_call_at"] == "2026-12-31T23:30:00+03:00"


def test_same_weekday_stays_unknown_and_partial_date_not_guessed():
    from mts_backend.agreements.dates import normalize_due

    call = SimpleNamespace(
        timezone="Europe/Minsk", call_at=datetime.fromisoformat("2026-10-16T10:00:00+03:00")
    )
    assert normalize_due(call, "до пятницы")["kind"] == "unknown"
    assert normalize_due(call, "до 15 января")["kind"] == "unknown"
    assert normalize_due(call, "2027-01-15")["date"] == "2027-01-15"
    with pytest.raises(BusinessError):
        normalize_due(call, "2027-02-30")
