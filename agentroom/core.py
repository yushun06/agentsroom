"""File-backed Agentroom store."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .schemas import validate_envelope

MAX_SEGMENT_SIZE = 10 * 1024 * 1024
MAX_SEGMENT_MESSAGES = 50_000


class AgentroomStore:
    def __init__(
        self,
        state_dir: str | os.PathLike[str] = ".state/agentroom",
        *,
        max_segment_size: int = MAX_SEGMENT_SIZE,
        max_segment_messages: int = MAX_SEGMENT_MESSAGES,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.max_segment_size = max_segment_size
        self.max_segment_messages = max_segment_messages
        self.rooms_dir = self.state_dir / "rooms"
        self.archive_dir = self.state_dir / "archive"
        self.cursors_dir = self.state_dir / "cursors"
        self.presence_dir = self.state_dir / "presence"
        self.dlq_dir = self.state_dir / "dlq"
        self.index_path = self.state_dir / "index.json"
        self.registry_path = self.state_dir / "registry.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for path in (self.rooms_dir, self.archive_dir, self.cursors_dir, self.presence_dir, self.dlq_dir):
            path.mkdir(parents=True, exist_ok=True)
        self._ensure_json(self.index_path, {"rooms": {}})
        self._ensure_json(self.registry_path, {"agents": {}})

    @staticmethod
    def encode_room_id(room_id: str) -> str:
        if not room_id or not isinstance(room_id, str):
            raise ValueError("room_id is required")
        return quote(room_id, safe=":-_.")

    def _segment_path(self, room_id: str, segment: int) -> Path:
        return self.rooms_dir / f"{self.encode_room_id(room_id)}.{segment:04d}.jsonl"

    def room_segments(self, room_id: str) -> list[Path]:
        prefix = f"{self.encode_room_id(room_id)}."
        return sorted(self.rooms_dir.glob(f"{prefix}[0-9][0-9][0-9][0-9].jsonl"))

    def active_segment(self, room_id: str) -> tuple[Path, int]:
        segments = self.room_segments(room_id)
        if not segments:
            return self._segment_path(room_id, 1), 1
        path = segments[-1]
        segment = int(path.stem.rsplit(".", 1)[1])
        return path, segment

    def append_message(self, room_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        validate_envelope(envelope)
        if envelope["roomId"] != room_id:
            raise ValueError("Envelope roomId does not match target room")
        path, segment = self.active_segment(room_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        if self._should_rotate(path):
            segment += 1
            path = self._segment_path(room_id, segment)
            path.touch(exist_ok=True)
        line = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle, fcntl.LOCK_UN)
        return {"message": envelope, "cursor": {"messageId": envelope["id"], "segment": segment}}

    def list_messages(
        self,
        room_id: str,
        *,
        since_cursor: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor_message_id = (since_cursor or {}).get("messageId")
        cursor_segment = int((since_cursor or {}).get("segment") or 1)
        found_cursor = cursor_message_id is None
        for path in self.room_segments(room_id):
            segment = int(path.stem.rsplit(".", 1)[1])
            if segment < cursor_segment:
                continue
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    message = json.loads(line)
                    if not found_cursor:
                        if message.get("id") == cursor_message_id:
                            found_cursor = True
                        continue
                    messages.append(message)
                    if limit is not None and len(messages) >= limit:
                        return messages
        return messages

    def save_cursor(self, agent_id: str, room_id: str, cursor: dict[str, Any]) -> None:
        path = self._cursor_path(agent_id)
        with self.locked_json(path, {"agentId": agent_id, "rooms": {}}) as data:
            data.setdefault("rooms", {})[room_id] = cursor

    def load_cursor(self, agent_id: str, room_id: str) -> dict[str, Any] | None:
        data = self.read_json(self._cursor_path(agent_id), {"agentId": agent_id, "rooms": {}})
        cursor = data.get("rooms", {}).get(room_id)
        return dict(cursor) if cursor else None

    def list_unread(self, agent_id: str, room_id: str, *, mark_read: bool = False) -> list[dict[str, Any]]:
        messages = self.list_messages(room_id, since_cursor=self.load_cursor(agent_id, room_id))
        if mark_read and messages:
            segment = self._segment_for_message(room_id, messages[-1]["id"])
            self.save_cursor(agent_id, room_id, {"messageId": messages[-1]["id"], "segment": segment})
        return messages

    def _segment_for_message(self, room_id: str, message_id: str) -> int:
        for path in self.room_segments(room_id):
            segment = int(path.stem.rsplit(".", 1)[1])
            with path.open("r", encoding="utf-8") as handle:
                if any(json.loads(line).get("id") == message_id for line in handle if line.strip()):
                    return segment
        raise ValueError(f"message {message_id} not found in {room_id}")

    def _should_rotate(self, path: Path) -> bool:
        if path.stat().st_size >= self.max_segment_size:
            return True
        if self.max_segment_messages <= 0:
            return False
        with path.open("r", encoding="utf-8") as handle:
            count = sum(1 for _ in handle)
        return count >= self.max_segment_messages

    def _cursor_path(self, agent_id: str) -> Path:
        if not agent_id:
            raise ValueError("agent_id is required")
        return self.cursors_dir / f"{quote(agent_id, safe=':-_.')}.json"

    @staticmethod
    def _ensure_json(path: Path, default: dict[str, Any]) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(default, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        self._ensure_json(path, default)
        with path.open("r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return dict(default)

    def locked_json(self, path: Path, default: dict[str, Any]) -> Iterator[dict[str, Any]]:
        return _LockedJson(path, default)


class _LockedJson:
    def __init__(self, path: Path, default: dict[str, Any]) -> None:
        self.path = path
        self.default = default
        self.handle: Any = None
        self.data: dict[str, Any] = {}

    def __enter__(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        self.handle.seek(0)
        raw = self.handle.read()
        self.data = json.loads(raw) if raw.strip() else dict(self.default)
        return self.data

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.handle.seek(0)
            self.handle.truncate()
            json.dump(self.data, self.handle, indent=2, sort_keys=True)
            self.handle.write("\n")
            self.handle.flush()
            os.fsync(self.handle.fileno())
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()
