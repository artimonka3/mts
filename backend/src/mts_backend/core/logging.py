"""Small JSON logger with an explicit allowlist of safe fields."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

SAFE_FIELDS = frozenset({"request_id", "method", "status_code", "ready", "mode"})


class SafeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Deliberately omit exc_info, args, URLs, headers, and arbitrary extra fields.
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": record.msg,
        }
        for field in SAFE_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("mts_backend")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(handler)


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    safe_fields = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
    logging.getLogger("mts_backend").log(level, event, extra=safe_fields)
