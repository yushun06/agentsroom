"""Schema helpers for Agentroom envelopes and A2A payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class SchemaError(ValueError):
    """Raised when an Agentroom schema is invalid."""


VALID_FORMATS = {"plain_text", "a2a", "system"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_message_id() -> str:
    return f"msg_{uuid4().hex}"


def new_trace_id() -> str:
    return f"trace_{uuid4().hex}"


def validate_agent_identity(value: dict[str, Any], field: str = "from") -> None:
    if not isinstance(value, dict):
        raise SchemaError(f"{field} must be an object")
    for key in ("agentId", "role", "adapter"):
        if not value.get(key) or not isinstance(value[key], str):
            raise SchemaError(f"{field}.{key} is required")


def validate_a2a_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise SchemaError("A2A payload must be an object")
    if payload.get("schema") != "agentroom.a2a.v1":
        raise SchemaError("A2A payload schema must be agentroom.a2a.v1")
    for key in ("type", "intent", "summary"):
        if not payload.get(key) or not isinstance(payload[key], str):
            raise SchemaError(f"A2A payload {key} is required")


def validate_envelope(envelope: dict[str, Any]) -> None:
    if not isinstance(envelope, dict):
        raise SchemaError("Envelope must be an object")
    for key in ("id", "ts", "roomId", "format", "from", "payload"):
        if key not in envelope:
            raise SchemaError(f"Envelope missing required field {key}")
    if envelope["format"] not in VALID_FORMATS:
        raise SchemaError(f"Unsupported format {envelope['format']}")
    validate_agent_identity(envelope["from"])
    if envelope.get("to") is not None:
        if not isinstance(envelope["to"], list):
            raise SchemaError("to must be a list")
        for index, target in enumerate(envelope["to"]):
            if not isinstance(target, dict):
                raise SchemaError(f"to[{index}] must be an object")
            if not target.get("agentId") and not target.get("role"):
                raise SchemaError(f"to[{index}] requires agentId or role")
    if not isinstance(envelope.get("metadata", {}), dict):
        raise SchemaError("metadata must be an object")
    if envelope["format"] == "plain_text":
        if not isinstance(envelope["payload"], dict) or not isinstance(envelope["payload"].get("text"), str):
            raise SchemaError("plain_text payload requires text")
    elif envelope["format"] == "a2a":
        validate_a2a_payload(envelope["payload"])
    elif envelope["format"] == "system" and (
        not isinstance(envelope["payload"], dict) or not isinstance(envelope["payload"].get("type"), str)
    ):
        raise SchemaError("system payload requires type")


def create_envelope(
    room_id: str,
    from_agent: dict[str, Any],
    payload: dict[str, Any],
    *,
    format: str = "plain_text",
    to: list[dict[str, Any]] | None = None,
    thread_id: str | None = None,
    reply_to: str | None = None,
    topic: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "id": new_message_id(),
        "ts": utc_now(),
        "roomId": room_id,
        "format": format,
        "from": from_agent,
        "to": to or [],
        "threadId": thread_id,
        "replyTo": reply_to,
        "topic": topic,
        "metadata": dict(metadata or {}),
        "payload": payload,
    }
    envelope["metadata"].setdefault("traceId", new_trace_id())
    validate_envelope(envelope)
    return envelope
