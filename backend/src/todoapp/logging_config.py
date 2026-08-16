"""Logging setup.

Development gets readable single-line output; production gets one JSON object per
record so a log shipper can parse it without a regex.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from todoapp.config import Settings

# Attributes present on every LogRecord; anything else was added by the caller
# via `extra=` and belongs in the structured payload.
_RESERVED_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Renders a record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialises ``record``, folding any ``extra=`` fields in at top level."""
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Installs a single stderr handler on the root logger."""
    handler = logging.StreamHandler(sys.stderr)
    if settings.is_production:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)-28s %(message)s", "%H:%M:%S")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # psycopg logs every pool checkout at DEBUG; too chatty even for us.
    logging.getLogger("psycopg.pool").setLevel(logging.INFO)
