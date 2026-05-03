"""HTTP integration tests for the Agentroom server."""

from __future__ import annotations

import json
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
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class HTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_dir = Path(__file__).parent / "_test_state_http"
        cls.tmp_dir.mkdir(exist_ok=True)
        store = AgentroomStore(cls.tmp_dir / "agentroom")
        cls.lifecycle = AgentroomLifecycle(store)
        cls.store = store

        class Handler(AgentroomHandler):
            room_lifecycle = cls.lifecycle
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
        import shutil

        if cls.tmp_dir.exists():
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path: str) -> dict[str, Any]:
        with request.urlopen(self._url(path)) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
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

    def test_health(self) -> None:
        result = self._get("/health")
        self.assertTrue(result["ok"])

    def test_metrics(self) -> None:
        from agentroom.observability.metrics import metrics as m

        m.messages_total.inc()
        with request.urlopen(self._url("/metrics")) as resp:
            text = resp.read().decode()
        self.assertIn("agentroom_messages_total", text)
        self.assertIn("text/plain", resp.headers.get("content-type", ""))

    def test_status(self) -> None:
        result = self._get("/status")
        self.assertIn("rooms", result)
        self.assertIn("agents", result)
        self.assertIn("dlq", result)
        self.assertIn("metrics", result)

    def test_create_and_discover_rooms(self) -> None:
        result, status = self._post("/rooms", {"roomId": "http:create-room", "topic": "HTTP test"})
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "active")

        rooms = self._get("/rooms?status=active&prefix=http:create")
        self.assertTrue(any(r["roomId"] == "http:create-room" for r in rooms))

    def test_post_and_list_messages(self) -> None:
        self._post("/rooms", {"roomId": "http:msg-room"})
        result, status = self._post(
            "/rooms/http:msg-room/messages",
            {
                "format": "plain_text",
                "from": {"agentId": "http-poster", "role": "worker", "adapter": "codex"},
                "text": "hello from HTTP",
            },
        )
        self.assertEqual(status, 201)

        messages = self._get("/rooms/http:msg-room/messages")
        self.assertTrue(any(m.get("payload", {}).get("text") == "hello from HTTP" for m in messages))

    def test_register_and_list_agents(self) -> None:
        result, status = self._post(
            "/agents/register",
            {
                "agentId": "http-tester",
                "role": "tester",
                "adapter": "codex",
                "webhook": "http://example.test/hook",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(result["agentId"], "http-tester")

        agents = self._get("/agents?role=tester")
        self.assertTrue(any(a["agentId"] == "http-tester" for a in agents))

    def test_join_leave_room(self) -> None:
        self._post("/rooms", {"roomId": "http:join-room"})
        self._post(
            "/agents/register",
            {
                "agentId": "http-joiner",
                "role": "worker",
                "adapter": "codex",
            },
        )
        result, _ = self._post(
            "/rooms/http:join-room/join",
            {
                "agentId": "http-joiner",
                "role": "worker",
                "adapter": "codex",
            },
        )
        self.assertIn("http:join-room", result.get("rooms", []))

        result, _ = self._post(
            "/rooms/http:join-room/leave",
            {
                "agentId": "http-joiner",
                "role": "worker",
                "adapter": "codex",
            },
        )
        self.assertNotIn("http:join-room", result.get("rooms", []))

    def test_heartbeat(self) -> None:
        self._post(
            "/agents/register",
            {
                "agentId": "http-beater",
                "role": "worker",
                "adapter": "codex",
            },
        )
        result, _ = self._post("/agents/http-beater/heartbeat", {"status": "busy"})
        self.assertEqual(result["status"], "busy")

    def test_archive_room(self) -> None:
        self._post("/rooms", {"roomId": "http:archive-room"})
        result, _ = self._post("/rooms/http:archive-room/archive", {})
        self.assertEqual(result["status"], "archived")

    def test_404(self) -> None:
        with self.assertRaises(error.HTTPError) as ctx:
            request.urlopen(self._url("/nonexistent"))
        self.assertEqual(ctx.exception.code, 404)

    def test_unread_messages(self) -> None:
        self._post("/rooms", {"roomId": "http:unread-room"})
        self._post(
            "/rooms/http:unread-room/messages",
            {
                "format": "plain_text",
                "from": {"agentId": "http-writer", "role": "worker", "adapter": "codex"},
                "text": "unread test",
            },
        )
        messages = self._get("/rooms/http:unread-room/messages?unread=true&agent=http-reader&mark_read=true")
        self.assertTrue(len(messages) >= 1)


if __name__ == "__main__":
    unittest.main()
