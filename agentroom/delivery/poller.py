"""Cursor-based polling helpers."""

from __future__ import annotations

from agentroom.core import AgentroomStore


def poll_unread(store: AgentroomStore, agent_id: str, room_id: str, *, mark_read: bool = True) -> list[dict]:
    return store.list_unread(agent_id, room_id, mark_read=mark_read)
