from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from mts_backend.exports.service import calendar_bytes, escape_ics, fold_ics, spreadsheet_bytes
from mts_backend.reminders.service import after_quiet_hours
from mts_backend.tasks.query import deadline, due_point, overdue
from mts_backend.tasks.routes import TRANSITIONS


def record(due=None, action="Отправить КП", **values):
    return SimpleNamespace(
        id="b42eeb5b-1b85-4ba8-a393-902306e7fa21",
        version=3,
        source="manual",
        data={
            "action": action,
            "due": due or {"kind": "date_only", "date": "2026-10-17", "timezone": "Europe/Minsk"},
            **values,
        },
        execution="open",
        verification="accepted",
        created_at=datetime(2026, 10, 14, tzinfo=UTC),
    )


def test_date_only_has_no_invented_time_and_expires_at_next_midnight():
    item = record()
    assert due_point(item.data).isoformat() == "2026-10-17T00:00:00+03:00"
    assert deadline(item.data).isoformat() == "2026-10-18T00:00:00+03:00"
    assert not overdue(item, datetime(2026, 10, 17, 20, 59, tzinfo=UTC))
    assert overdue(item, datetime(2026, 10, 17, 21, tzinfo=UTC))
    item.execution = "done"
    assert not overdue(item, datetime(2026, 10, 18, tzinfo=UTC))


def test_calendar_stable_uid_sequence_crlf_escaping_and_unknown_skip():
    item = record(action="КП, договор; первая\nвторая\\строка")
    unknown = record(due={"kind": "unknown"})
    body, skipped = calendar_bytes([item, unknown])
    text = body.decode()
    assert "UID:b42eeb5b-1b85-4ba8-a393-902306e7fa21@mts-mvp.local" in text
    assert "SEQUENCE:3\r\n" in text
    assert "DTSTART;VALUE=DATE:20261017\r\nDTEND;VALUE=DATE:20261018" in text
    assert "DTSTART:20261017T" not in text
    assert "КП\\, договор\\; первая\\nвторая\\\\строка" in text.replace("\r\n ", "")
    assert skipped == [unknown.id]
    assert calendar_bytes([])[0].endswith(b"END:VCALENDAR\r\n")


def test_utf8_folding_preserves_codepoints_and_75_octet_limit():
    line = "SUMMARY:" + "Договорённость🌲" * 50
    folded = fold_ics(line)
    assert folded.replace("\r\n ", "") == line
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert escape_ics("a\r\nb") == "a\\nb"


@pytest.mark.parametrize("action", ['=HYPERLINK("http://bad")', "+1+1", "-2+3", "@SUM(A1)"])
def test_xlsx_user_text_is_never_formula(action):
    from openpyxl import load_workbook

    workbook = load_workbook(BytesIO(spreadsheet_bytes([record(action=action)])))
    assert workbook.active["C2"].value == action
    assert workbook.active["C2"].data_type == "s"
    assert workbook.active.freeze_panes == "A2"


def test_quiet_hours_over_midnight():
    now = datetime(2026, 10, 14, 20, tzinfo=UTC)  # 23:00 Minsk
    policy = {"timezone": "Europe/Minsk", "quiet_hours": {"start": 22, "end": 8}}
    assert after_quiet_hours(now, policy).isoformat() == "2026-10-15T08:00:00+03:00"
    assert after_quiet_hours(datetime(2026, 10, 14, 10, tzinfo=UTC), policy).hour == 10


def test_transitions_are_explicit():
    assert TRANSITIONS[("open", "complete")] == "done"
    assert TRANSITIONS[("done", "reopen")] == "open"
    assert ("done", "start") not in TRANSITIONS
