"""Dead-letter queue persistence and retry for failed webhook deliveries."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ..observability.logger import get_logger
from ..observability.metrics import metrics
from ..schemas import utc_now
from ._http import post_json

logger = get_logger("dlq")

MAX_RETRIES = 4
RETRY_DELAYS: list[float] = [1.0, 5.0, 30.0]  # attempts 1, 2, 3


def enqueue_dlq(state_dir: str | Path, agent_id: str, message: dict[str, Any], *, error: str) -> Path:
    """Write a failed delivery to the DLQ."""
    base = Path(state_dir) / "dlq" / agent_id
    base.mkdir(parents=True, exist_ok=True)
    message_id = message.get("id", "unknown")
    path = base / f"{message_id}.json"
    entry = {
        "agentId": agent_id,
        "messageId": message_id,
        "payload": message,
        "attempts": 1,
        "lastError": error,
        "updatedAt": utc_now(),
    }
    path.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics.dlq_depth.inc(labels={"agent": agent_id})
    logger.warning("DLQ enqueue", extra={"agentId": agent_id, "messageId": message_id})
    return path


def read_dlq_entries(state_dir: str | Path) -> list[dict[str, Any]]:
    """Read all DLQ entries across all agents."""
    dlq_dir = Path(state_dir) / "dlq"
    if not dlq_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for agent_dir in sorted(dlq_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        for entry_path in sorted(agent_dir.glob("*.json")):
            try:
                entries.append(json.loads(entry_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
    return entries


def _dlq_path(state_dir: str | Path, agent_id: str, message_id: str) -> Path:
    return Path(state_dir) / "dlq" / agent_id / f"{message_id}.json"


def _remove_dlq_entry(state_dir: str | Path, agent_id: str, message_id: str) -> None:
    path = _dlq_path(state_dir, agent_id, message_id)
    if path.exists():
        path.unlink()
        metrics.dlq_depth.dec(labels={"agent": agent_id})


def _update_dlq_entry(state_dir: str | Path, entry: dict[str, Any], *, error: str) -> None:
    path = _dlq_path(state_dir, entry["agentId"], entry["messageId"])
    entry["attempts"] += 1
    entry["lastError"] = error
    entry["updatedAt"] = utc_now()
    path.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def retry_dlq(
    state_dir: str | Path,
    *,
    webhook_timeout: float = 5.0,
    mark_unhealthy_fn: Any | None = None,
    webhook_lookup_fn: Any | None = None,
) -> None:
    """Single pass: scan DLQ, retry failed deliveries, mark exhausted agents unhealthy.

    Args:
        state_dir: Path to the agentroom state directory.
        webhook_timeout: HTTP timeout for retry delivery attempts.
        mark_unhealthy_fn: Optional async callable(agent_id) to mark an agent unhealthy.
        webhook_lookup_fn: Optional callable(agent_id) -> str | None that returns
            the webhook URL for an agent. If not provided, the webhook URL is
            read from the DLQ entry's payload metadata.
    """
    entries = read_dlq_entries(state_dir)
    if not entries:
        return

    logger.info("DLQ retry scan", extra={"event": f"scanning {len(entries)} DLQ entries"})

    for entry in entries:
        agent_id = entry["agentId"]
        message_id = entry["messageId"]
        attempts = entry.get("attempts", 1)

        # Look up webhook: prefer registry lookup, fall back to entry metadata
        webhook_url = None
        if webhook_lookup_fn:
            webhook_url = webhook_lookup_fn(agent_id)
        if not webhook_url:
            webhook_url = entry.get("webhook")

        if not webhook_url:
            logger.warning("DLQ entry has no webhook, removing", extra={"agentId": agent_id, "messageId": message_id})
            _remove_dlq_entry(state_dir, agent_id, message_id)
            continue

        try:
            await asyncio.to_thread(post_json, webhook_url, entry["payload"], webhook_timeout)
            _remove_dlq_entry(state_dir, agent_id, message_id)
            metrics.dlq_retries_total.inc()
            logger.info("DLQ retry succeeded", extra={"agentId": agent_id, "messageId": message_id})
        except Exception as exc:
            metrics.dlq_retries_total.inc()
            if attempts >= MAX_RETRIES:
                logger.error(
                    "DLQ retries exhausted, marking agent unhealthy",
                    extra={"agentId": agent_id, "messageId": message_id},
                )
                _remove_dlq_entry(state_dir, agent_id, message_id)
                if mark_unhealthy_fn:
                    if asyncio.iscoroutinefunction(mark_unhealthy_fn):
                        await mark_unhealthy_fn(agent_id)
                    else:
                        mark_unhealthy_fn(agent_id)
            else:
                _update_dlq_entry(state_dir, entry, error=str(exc))
                delay = RETRY_DELAYS[min(attempts - 1, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"DLQ retry failed, next retry in {delay}s",
                    extra={"agentId": agent_id, "messageId": message_id},
                )


async def retry_loop(
    state_dir: str | Path,
    *,
    interval: float = 10.0,
    webhook_timeout: float = 5.0,
    mark_unhealthy_fn: Any | None = None,
    webhook_lookup_fn: Any | None = None,
) -> None:
    """Background loop that periodically scans and retries DLQ entries."""
    logger.info("DLQ retry loop started", extra={"event": f"interval={interval}s"})
    while True:
        try:
            await retry_dlq(
                state_dir,
                webhook_timeout=webhook_timeout,
                mark_unhealthy_fn=mark_unhealthy_fn,
                webhook_lookup_fn=webhook_lookup_fn,
            )
        except Exception as exc:
            logger.error(f"DLQ retry loop error: {exc}")
        await asyncio.sleep(interval)
