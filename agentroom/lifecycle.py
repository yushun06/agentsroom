"""Room lifecycle, discovery, and agent registry management."""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path
from typing import Any

from urllib.parse import quote

from .core import AgentroomStore
from .schemas import create_envelope, utc_now

SYSTEM_AGENT = {"agentId": "agentroom", "role": "system", "adapter": "agentroom"}


class AgentroomLifecycle:
    def __init__(self, store: AgentroomStore | None = None) -> None:
        self.store = store or AgentroomStore()

    def create_room(self, room_id: str, *, topic: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        # Validate room_id before mutating the index — encode_room_id rejects empty/invalid IDs
        self.store.encode_room_id(room_id)
        now = utc_now()
        with self.store.locked_json(self.store.index_path, {"rooms": {}}) as index:
            rooms = index.setdefault("rooms", {})
            if room_id in rooms and rooms[room_id].get("status") != "deleted":
                raise ValueError(f"room already exists: {room_id}")
            rooms[room_id] = {
                "roomId": room_id,
                "status": "active",
                "topic": topic,
                "metadata": metadata or {},
                "createdAt": now,
                "updatedAt": now,
            }
        envelope = create_envelope(
            room_id,
            SYSTEM_AGENT,
            {"type": "room.created", "topic": topic, "metadata": metadata or {}},
            format="system",
            topic=topic,
        )
        self.store.append_message(room_id, envelope)
        return self.get_room(room_id)

    def get_room(self, room_id: str) -> dict[str, Any]:
        room = self.store.read_json(self.store.index_path, {"rooms": {}}).get("rooms", {}).get(room_id)
        if not room:
            raise KeyError(f"room not found: {room_id}")
        return dict(room)

    def discover_rooms(self, *, status: str | None = "active", prefix: str | None = None) -> list[dict[str, Any]]:
        rooms = self.store.read_json(self.store.index_path, {"rooms": {}}).get("rooms", {})
        result = []
        for room in rooms.values():
            if status and room.get("status") != status:
                continue
            if prefix and not room.get("roomId", "").startswith(prefix):
                continue
            result.append(dict(room))
        return sorted(result, key=lambda value: value["roomId"])

    def archive_room(self, room_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.store.locked_json(self.store.index_path, {"rooms": {}}) as index:
            room = index.setdefault("rooms", {}).get(room_id)
            if not room:
                raise KeyError(f"room not found: {room_id}")
            if room.get("status") == "archived":
                return dict(room)
            room["status"] = "archived"
            room["archivedAt"] = now
            room["updatedAt"] = now
        envelope = create_envelope(room_id, SYSTEM_AGENT, {"type": "room.archived"}, format="system")
        self.store.append_message(room_id, envelope)
        self._compress_room_segments(room_id)
        return self.get_room(room_id)

    def register_agent(
        self,
        agent_id: str,
        *,
        role: str,
        adapter: str,
        capabilities: list[str] | None = None,
        webhook: str | None = None,
        server: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        agent = {
            "agentId": agent_id,
            "role": role,
            "adapter": adapter,
            "capabilities": capabilities or [],
            "webhook": webhook,
            "server": server,
            "metadata": metadata or {},
            "status": "online",
            "lastSeenAt": now,
            "registeredAt": now,
        }
        with self.store.locked_json(self.store.registry_path, {"agents": {}}) as registry:
            existing = registry.setdefault("agents", {}).get(agent_id, {})
            agent["registeredAt"] = existing.get("registeredAt", now)
            registry["agents"][agent_id] = agent
        self._save_presence(agent_id, "online", rooms=existing.get("rooms", []) if "existing" in locals() else [])
        return agent

    def list_agents(self, *, role: str | None = None, capability: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        agents = self.store.read_json(self.store.registry_path, {"agents": {}}).get("agents", {})
        result = []
        for agent in agents.values():
            if role and agent.get("role") != role:
                continue
            if status and agent.get("status") != status:
                continue
            if capability and capability not in agent.get("capabilities", []):
                continue
            result.append(dict(agent))
        return sorted(result, key=lambda value: value["agentId"])

    def heartbeat(self, agent_id: str, *, status: str = "online") -> dict[str, Any]:
        now = utc_now()
        with self.store.locked_json(self.store.registry_path, {"agents": {}}) as registry:
            agent = registry.setdefault("agents", {}).get(agent_id)
            if not agent:
                raise KeyError(f"agent not found: {agent_id}")
            agent["status"] = status
            agent["lastSeenAt"] = now
        presence = self._save_presence(agent_id, status)
        return presence

    def join_room(self, room_id: str, agent_id: str, *, role: str, adapter: str, capabilities: list[str] | None = None) -> dict[str, Any]:
        self._assert_room_active(room_id)
        agents = self.store.read_json(self.store.registry_path, {"agents": {}}).get("agents", {})
        if agent_id not in agents:
            self.register_agent(agent_id, role=role, adapter=adapter, capabilities=capabilities or [])
        presence = self._save_presence(agent_id, "online", add_room=room_id)
        envelope = create_envelope(
            room_id,
            {"agentId": agent_id, "role": role, "adapter": adapter},
            {"type": "agent.joined", "capabilities": capabilities or []},
            format="system",
        )
        self.store.append_message(room_id, envelope)
        return presence

    def leave_room(self, room_id: str, agent_id: str, *, role: str = "agent", adapter: str = "unknown") -> dict[str, Any]:
        self._assert_room_exists(room_id)
        presence = self._save_presence(agent_id, "offline", remove_room=room_id)
        envelope = create_envelope(
            room_id,
            {"agentId": agent_id, "role": role, "adapter": adapter},
            {"type": "agent.left"},
            format="system",
        )
        self.store.append_message(room_id, envelope)
        return presence

    def post_text(
        self,
        room_id: str,
        *,
        text: str,
        agent_id: str,
        role: str,
        adapter: str,
        to: list[dict[str, Any]] | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        self._assert_room_active(room_id)
        envelope = create_envelope(
            room_id,
            {"agentId": agent_id, "role": role, "adapter": adapter},
            {"text": text},
            format="plain_text",
            to=to,
            topic=topic,
        )
        return self.store.append_message(room_id, envelope)

    def post_a2a(
        self,
        room_id: str,
        *,
        payload: dict[str, Any],
        agent_id: str,
        role: str,
        adapter: str,
        to: list[dict[str, Any]] | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        self._assert_room_active(room_id)
        envelope = create_envelope(
            room_id,
            {"agentId": agent_id, "role": role, "adapter": adapter},
            payload,
            format="a2a",
            to=to,
            topic=topic,
        )
        return self.store.append_message(room_id, envelope)

    def status(self) -> dict[str, Any]:
        rooms = self.store.read_json(self.store.index_path, {"rooms": {}}).get("rooms", {})
        agents = self.store.read_json(self.store.registry_path, {"agents": {}}).get("agents", {})
        room_values = list(rooms.values())
        agent_values = list(agents.values())
        return {
            "ts": utc_now(),
            "rooms": {
                "total": len(room_values),
                "active": sum(1 for room in room_values if room.get("status") == "active"),
                "archived": sum(1 for room in room_values if room.get("status") == "archived"),
            },
            "agents": {
                "registered": len(agent_values),
                "healthy": sum(1 for agent in agent_values if agent.get("status") in {"online", "busy"}),
                "unhealthy": sum(1 for agent in agent_values if agent.get("status") == "unhealthy"),
                "unhealthy_ids": [agent["agentId"] for agent in agent_values if agent.get("status") == "unhealthy"],
            },
            "messages": {"total": sum(self._room_message_count(room["roomId"]) for room in room_values)},
            "dlq": {"pending": len(list(self.store.dlq_dir.glob("*/*.json")))},
        }

    def _room_message_count(self, room_id: str) -> int:
        total = 0
        for path in self.store.room_segments(room_id):
            with path.open("r", encoding="utf-8") as handle:
                total += sum(1 for line in handle if line.strip())
        return total

    def _save_presence(
        self,
        agent_id: str,
        status: str,
        *,
        rooms: list[str] | None = None,
        add_room: str | None = None,
        remove_room: str | None = None,
    ) -> dict[str, Any]:
        path = self.store.presence_dir / f"{quote(agent_id, safe=':-_.')}.json"
        with self.store.locked_json(path, {"agentId": agent_id, "rooms": []}) as presence:
            presence["agentId"] = agent_id
            presence["status"] = status
            presence["lastSeenAt"] = utc_now()
            current_rooms = set(rooms if rooms is not None else presence.get("rooms", []))
            if add_room:
                current_rooms.add(add_room)
            if remove_room:
                current_rooms.discard(remove_room)
            presence["rooms"] = sorted(current_rooms)
        return self.store.read_json(path, {"agentId": agent_id, "rooms": []})

    def _assert_room_exists(self, room_id: str) -> None:
        self.get_room(room_id)

    def _assert_room_active(self, room_id: str) -> None:
        room = self.get_room(room_id)
        if room.get("status") != "active":
            raise ValueError(f"room is not active: {room_id}")

    def _compress_room_segments(self, room_id: str) -> None:
        target_dir = self.store.archive_dir / self.store.encode_room_id(room_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in self.store.room_segments(room_id):
            archive_path = target_dir / f"{path.name}.gz"
            if archive_path.exists():
                continue
            with path.open("rb") as source, gzip.open(archive_path, "wb") as target:
                shutil.copyfileobj(source, target)
