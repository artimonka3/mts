import json
import logging

from mts_backend.core.logging import SafeJsonFormatter


def test_log_formatter_omits_arbitrary_fields_and_exception_details():
    record = logging.LogRecord(
        "mts_backend",
        logging.ERROR,
        __file__,
        1,
        "request_failed",
        ("private-body",),
        None,
    )
    record.request_id = "demo-123"
    record.url = "https://private-host/private-path?token=private-token"
    record.body = "private-body"
    record.exc_text = "private-error"
    formatted = SafeJsonFormatter().format(record)
    payload = json.loads(formatted)
    assert payload["event"] == "request_failed"
    assert payload["request_id"] == "demo-123"
    for sensitive in ("private-body", "private-host", "private-token", "private-error"):
        assert sensitive not in formatted
