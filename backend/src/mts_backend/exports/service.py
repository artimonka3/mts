from datetime import UTC, date, datetime, timedelta
from io import BytesIO

from mts_backend.tasks.query import deadline


def escape_ics(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ics(line):
    # RFC5545 counts octets, so never cut a Cyrillic UTF-8 character in half.
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return "\r\n".join(parts)


def utc_stamp(value):
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def calendar_bytes(agreements, now=None):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MTS MVP//Tasks//RU", "CALSCALE:GREGORIAN"]
    skipped = []
    for item in agreements:
        due = item.data.get("due", {})
        if (
            deadline(item.data) is None
            or due.get("ambiguous", False)
            or (item.data.get("condition") and not item.data.get("condition_resolution"))
        ):
            skipped.append(item.id)
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item.id}@mts-mvp.local",
            f"SEQUENCE:{item.version}",
            f"DTSTAMP:{utc_stamp(now or item.created_at)}",
            "SUMMARY:"
            + escape_ics(("" if due["kind"] == "interval" else "Срок: ") + item.data["action"]),
            "STATUS:" + ("CANCELLED" if item.execution == "cancelled" else "CONFIRMED"),
            "DESCRIPTION:" + escape_ics(f"Состояние: {item.execution}; источник: {item.source}"),
        ]
        if due["kind"] == "date_only":
            day = date.fromisoformat(due["date"])
            lines += [
                f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            ]
        elif due["kind"] == "instant":
            instant = datetime.fromisoformat(due["at"].replace("Z", "+00:00"))
            lines += [f"DTSTART:{utc_stamp(instant)}"]
        else:
            start = datetime.fromisoformat(due["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(due["end"].replace("Z", "+00:00"))
            lines += [f"DTSTART:{utc_stamp(start)}", f"DTEND:{utc_stamp(end)}"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_ics(line) for line in lines) + "\r\n").encode("utf-8"), skipped


def spreadsheet_bytes(agreements, details=None):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Договорённости"
    sheet.append(
        [
            "ID",
            "Версия",
            "Договорённость",
            "Клиент",
            "Кто",
            "Кому",
            "Срок",
            "Приоритет",
            "Состояние",
            "Теги",
            "Звонок",
            "Источник",
        ]
    )
    for item in agreements:
        due = item.data.get("due", {})
        due_text = due.get("date") or due.get("at") or due.get("end") or "Не указан"
        extra = (details or {}).get(item.id, {})
        row = [
            item.id,
            item.version,
            item.data["action"],
            extra.get("client", ""),
            extra.get("obligor", ""),
            extra.get("recipient", ""),
            due_text,
            item.data.get("priority", "normal"),
            item.execution,
            extra.get("tags", ""),
            "/calls/" + getattr(item, "call_id", ""),
            item.source,
        ]
        sheet.append(row)
        # Explicit text cells disarm =,+,-,@ formula injection, including leading whitespace.
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in {
        "A": 38,
        "B": 10,
        "C": 65,
        "D": 28,
        "E": 25,
        "F": 25,
        "G": 30,
        "H": 15,
        "I": 18,
        "J": 30,
        "K": 45,
        "L": 15,
    }.items():
        sheet.column_dimensions[column].width = width
    result = BytesIO()
    workbook.save(result)
    return result.getvalue()
