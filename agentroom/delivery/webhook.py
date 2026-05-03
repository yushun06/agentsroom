"""Async webhook fan-out and dispatcher integration."""

from __future__ import annotations

import asyncio
from typing import Any

from ..observability.logger import get_logger
from ..observability.metrics import Timer, metrics
from ._http import post_json
from .dlq import enqueue_dlq

logger = get_logger("webhook")


async def fan_out(
    message: dict[str, Any],
    subscribers: list[dict[str, Any]],
    *,
    concurrency: int = 50,
    timeout: float = 5.0,
    state_dir: str | None = None,
) -> list[Exception | None]:
    """Deliver a message to all subscribers concurrently.

    Failed deliveries are enqueued to the DLQ if state_dir is provided.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def deliver(subscriber: dict[str, Any]) -> Exception | None:
        agent_id = subscriber.get("agentId", "unknown")
        webhook_url = subscriber.get("webhook")
        if not webhook_url:
            return None
        async with semaphore:
            with Timer(metrics.webhook_delivery_duration):
                try:
                    await asyncio.to_thread(post_json, webhook_url, message, timeout)
                    metrics.webhook_deliveries_total.inc(labels={"status": "success"})
                    logger.info(
                        "webhook delivered",
                        extra={"agentId": agent_id, "messageId": message.get("id"), "roomId": message.get("roomId")},
                    )
                    return None
                except Exception as exc:
                    metrics.webhook_deliveries_total.inc(labels={"status": "failure"})
                    logger.warning(
                        f"webhook failed: {exc}",
                        extra={"agentId": agent_id, "messageId": message.get("id")},
                    )
                    if state_dir:
                        enqueue_dlq(state_dir, agent_id, message, error=str(exc), webhook=webhook_url)
                    return exc

    return await asyncio.gather(*(deliver(sub) for sub in subscribers))


def get_subscribers_for_room(
    registry: dict[str, Any],
    room_id: str,
    *,
    exclude_agent: str | None = None,
    store: Any = None,
) -> list[dict[str, Any]]:
    """Return webhook-capable agents subscribed to a room.

    An agent is considered subscribed if it has the room in its presence
    and has a webhook URL configured. If store is provided, presence is
    read from disk; otherwise all online/busy agents with webhooks are
    returned (backward-compatible fallback).
    """
    agents = registry.get("agents", {})
    subscribers: list[dict[str, Any]] = []
    for agent in agents.values():
        agent_id = agent.get("agentId", "")
        if exclude_agent and agent_id == exclude_agent:
            continue
        if not agent.get("webhook") or agent.get("status") not in ("online", "busy"):
            continue
        # Check room membership via presence
        if store is not None:
            presence_path = store.presence_dir / f"{_safe_filename(agent_id)}.json"
            presence = store.read_json(presence_path, {"rooms": []})
            if room_id not in presence.get("rooms", []):
                continue
        subscribers.append(agent)
    return subscribers


def _safe_filename(agent_id: str) -> str:
    """Encode agent_id for safe filesystem use (mirrors core._cursor_path)."""
    from urllib.parse import quote

    return quote(agent_id, safe=":-_.")


async def dispatch_after_append(
    message: dict[str, Any],
    store: Any,
    *,
    concurrency: int = 50,
    timeout: float = 5.0,
) -> list[Exception | None] | None:
    """Auto-dispatch a message to webhook subscribers after appending.

    Returns None if no subscribers are found (not an error).
    """
    registry = store.read_json(store.registry_path, {"agents": {}})
    room_id = message.get("roomId", "")
    sender_id = message.get("from", {}).get("agentId")
    subscribers = get_subscribers_for_room(registry, room_id, exclude_agent=sender_id, store=store)
    if not subscribers:
        return None
    return await fan_out(
        message,
        subscribers,
        concurrency=concurrency,
        timeout=timeout,
        state_dir=str(store.state_dir),
    )
