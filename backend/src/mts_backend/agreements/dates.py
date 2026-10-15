"""Small explicit date helper. This does not extract agreements or use an LLM."""

import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from mts_backend.core.business import BusinessError

WEEKDAYS = {
    "понедельник": 0,
    "вторник": 1,
    "среду": 2,
    "четверг": 3,
    "пятницу": 4,
    "субботу": 5,
    "воскресенье": 6,
}


def normalize_due(call, phrase):
    local = call.call_at.astimezone(ZoneInfo(call.timezone))
    value = " ".join(phrase.lower().strip().split())
    result = {
        "kind": "unknown",
        "timezone": call.timezone,
        "original_text": phrase,
        "basis_call_at": local.isoformat(),
        "normalization_source": "manual",
        "ambiguous": True,
        "ambiguity_reasons": ["phrase_not_supported"],
    }
    target = None
    if value == "завтра":
        target = local.date() + timedelta(days=1)
    elif match := re.fullmatch(r"через (\d{1,4}) (?:день|дня|дней)", value):
        days = int(match[1])
        if days <= 3650:
            target = local.date() + timedelta(days=days)
    elif value.startswith("до ") and value[3:] in WEEKDAYS:
        delta = (WEEKDAYS[value[3:]] - local.weekday()) % 7
        if delta == 0:
            result["ambiguity_reasons"] = ["weekday_same_day_ambiguous"]
        else:
            target = local.date() + timedelta(days=delta)
    elif re.fullmatch(r"(?:до )?\d{4}-\d{2}-\d{2}", value):
        try:
            target = date.fromisoformat(value.removeprefix("до "))
        except ValueError:
            raise BusinessError(422, "invalid_due", "The date does not exist.") from None
    if target is not None:
        result.update(
            kind="date_only", date=target.isoformat(), ambiguous=False, ambiguity_reasons=[]
        )
        if target < local.date():
            result.update(
                ambiguous=True, ambiguity_reasons=["deadline_before_call_requires_review"]
            )
    return result
