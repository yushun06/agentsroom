"""End-to-end test for Agentroom running on localhost.

Spins up a real HTTP server on 127.0.0.1 and exercises the full
multi-agent lifecycle: registration, room creation, join, messaging,
unread cursors, heartbeats, archiving, and status/metrics.
"""

from __future__ import annotations

import json
import shutil
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request

from agentroom.core import AgentroomStore
from agentroom.lifecycle import AgentroomLifecycle
from agentroom.server import AgentroomHandler


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class E2ELocalhostTests(unittest.TestCase):
    """Full end-to-end test against a local Agentroom server."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_dir = Path(__file__).parent / "_test_state_e2e"
        if cls.tmp_dir.exists():
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)
        cls.tmp_dir.mkdir(parents=True, exist_ok=True)

        store = AgentroomStore(cls.tmp_dir / "agentroom")
        lifecycle = AgentroomLifecycle(store)
        cls.lifecycle = lifecycle
        cls.store = store

        class Handler(AgentroomHandler):
            room_lifecycle = lifecycle
            room_store = store
            dlq_loop = None  # type: ignore[assignment]

        cls.port = _free_port()
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        if cls.tmp_dir.exists():
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path: str) -> Any:
        with request.urlopen(self._url(path)) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict[str, Any]) -> tuple[Any, int]:
        raw = json.dumps(body).encode("utf-8")
        req = request.Request(
            self._url(path),
            data=raw,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req) as resp:
                return json.loads(resp.read()), resp.status
        except error.HTTPError as exc:
            return json.loads(exc.read()), exc.code

    # ------------------------------------------------------------------ #
    # End-to-end scenario
    # ------------------------------------------------------------------ #

    def test_full_agent_lifecycle(self) -> None:
        """Register agents, create a room, exchange messages, and archive."""
        # 1. Health check
        health = self._get("/health")
        self.assertTrue(health["ok"])

        # 2. Register two agents
        for agent_id in ("coordinator", "worker-1"):
            result, status = self._post(
                "/agents/register",
                {
                    "agentId": agent_id,
                    "role": "worker" if "worker" in agent_id else "coordinator",
                    "adapter": "codex",
                    "capabilities": ["planning", "execution"],
                },
            )
            self.assertEqual(status, 201)
            self.assertEqual(result["agentId"], agent_id)

        # 3. Create a coordination room
        room, status = self._post(
            "/rooms",
            {
                "roomId": "e2e:project-alpha",
                "topic": "End-to-end project room",
                "metadata": {"priority": "high"},
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(room["status"], "active")

        # 4. Agents join the room
        for agent_id in ("coordinator", "worker-1"):
            result, _ = self._post(
                "/rooms/e2e:project-alpha/join",
                {
                    "agentId": agent_id,
                    "role": "worker" if "worker" in agent_id else "coordinator",
                    "adapter": "codex",
                },
            )
            self.assertIn("e2e:project-alpha", result.get("rooms", []))

        # 5. Post messages (plain text and A2A)
        result, status = self._post(
            "/rooms/e2e:project-alpha/messages",
            {
                "format": "plain_text",
                "from": {"agentId": "coordinator", "role": "coordinator", "adapter": "codex"},
                "text": "Kickoff task for project alpha",
            },
        )
        self.assertEqual(status, 201)
        self.assertIn("message", result)

        result, status = self._post(
            "/rooms/e2e:project-alpha/messages",
            {
                "format": "a2a",
                "from": {"agentId": "worker-1", "role": "worker", "adapter": "codex"},
                "payload": {
                    "schema": "agentroom.a2a.v1",
                    "type": "task.update",
                    "intent": "inform",
                    "summary": "Acknowledged — starting execution",
                },
            },
        )
        self.assertEqual(status, 201)

        # 6. List all messages
        messages = self._get("/rooms/e2e:project-alpha/messages")
        texts = []
        for m in messages:
            payload = m.get("payload", {})
            if m.get("format") == "a2a":
                texts.append(payload.get("summary"))
            else:
                texts.append(payload.get("text") or m.get("text"))
        self.assertIn("Kickoff task for project alpha", texts)
        self.assertIn("Acknowledged — starting execution", texts)

        # 7. Unread messages for a new observer agent
        self._post(
            "/agents/register",
            {
                "agentId": "observer",
                "role": "auditor",
                "adapter": "codex",
            },
        )
        self._post(
            "/rooms/e2e:project-alpha/join",
            {
                "agentId": "observer",
                "role": "auditor",
                "adapter": "codex",
            },
        )
        unread = self._get("/rooms/e2e:project-alpha/messages?unread=true&agent=observer&mark_read=true")
        self.assertGreaterEqual(len(unread), 2)

        # 8. Second unread fetch should return nothing (already marked read)
        unread2 = self._get("/rooms/e2e:project-alpha/messages?unread=true&agent=observer&mark_read=true")
        self.assertEqual(len(unread2), 0)

        # 9. Heartbeats
        for agent_id in ("coordinator", "worker-1"):
            result, _ = self._post(f"/agents/{agent_id}/heartbeat", {"status": "busy"})
            self.assertEqual(result["status"], "busy")

        # 10. Status overview
        status_result = self._get("/status")
        self.assertGreaterEqual(status_result["rooms"]["active"], 1)
        self.assertGreaterEqual(status_result["agents"]["registered"], 3)
        self.assertIn("metrics", status_result)

        # 11. Metrics endpoint returns Prometheus text
        with request.urlopen(self._url("/metrics")) as resp:
            metrics_text = resp.read().decode()
        self.assertIn("agentroom_messages_total", metrics_text)

        # 12. Archive the room
        result, _ = self._post("/rooms/e2e:project-alpha/archive", {})
        self.assertEqual(result["status"], "archived")

        archived_rooms = self._get("/rooms?status=archived")
        self.assertTrue(any(r["roomId"] == "e2e:project-alpha" for r in archived_rooms))

    def test_room_discovery_and_agent_filtering(self) -> None:
        """Create multiple rooms and agents, then filter via API."""
        for i in range(3):
            self._post(
                "/rooms",
                {
                    "roomId": f"e2e:discover-{i}",
                    "topic": f"Discovery room {i}",
                },
            )

        for i in range(2):
            self._post(
                "/agents/register",
                {
                    "agentId": f"e2e-agent-{i}",
                    "role": "tester",
                    "adapter": "codex",
                },
            )

        rooms = self._get("/rooms?prefix=e2e:discover")
        self.assertEqual(len(rooms), 3)

        agents = self._get("/agents?role=tester")
        self.assertEqual(len(agents), 2)

        # Non-matching prefix returns empty
        empty = self._get("/rooms?prefix=nonexistent")
        self.assertEqual(len(empty), 0)

    def test_error_cases(self) -> None:
        """Verify graceful error handling for invalid requests."""
        # 404 on unknown path
        with self.assertRaises(error.HTTPError) as ctx:
            request.urlopen(self._url("/does-not-exist"))
        self.assertEqual(ctx.exception.code, 404)

        # Missing agent parameter for unread messages
        self._post("/rooms", {"roomId": "e2e:error-room"})
        with self.assertRaises(error.HTTPError) as ctx:
            self._get("/rooms/e2e:error-room/messages?unread=true")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
