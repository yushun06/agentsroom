"""Structured JSON logging for Agentroom."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "component": record.name,
            "event": record.getMessage(),
        }
        for key in ("roomId", "agentId", "messageId", "latencyMs", "traceId"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, sort_keys=True)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the agentroom logger with JSON output to stdout."""
    logger = logging.getLogger("agentroom")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    return logger


def get_logger(component: str) -> logging.Logger:
    """Get a child logger for a specific component."""
    return logging.getLogger(f"agentroom.{component}")
