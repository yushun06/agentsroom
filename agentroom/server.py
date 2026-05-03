"""HTTP API for the Agentroom central node."""

from __future__ import annotations

import asyncio
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .core import AgentroomStore
from .delivery.dlq import retry_loop
from .delivery.webhook import dispatch_after_append
from .lifecycle import AgentroomLifecycle
from .observability.logger import get_logger, setup_logging
from .observability.metrics import Timer, metrics

logger = get_logger("server")


def serve(host: str = "127.0.0.1", port: int = 8765, state_dir: str = ".state/agentroom", *, log_level: str = "INFO") -> None:
    """Start the Agentroom central node HTTP server."""
    setup_logging(log_level)
    store = AgentroomStore(state_dir)
    lifecycle = AgentroomLifecycle(store)

    # Start background DLQ retry loop
    dlq_event_loop = asyncio.new_event_loop()

    def _webhook_lookup(agent_id: str) -> str | None:
        """Look up an agent's webhook URL from the registry."""
        registry = store.read_json(store.registry_path, {"agents": {}})
        return registry.get("agents", {}).get(agent_id, {}).get("webhook")

    def _run_dlq_loop() -> None:
        asyncio.set_event_loop(dlq_event_loop)
        dlq_event_loop.run_until_complete(
            retry_loop(
                store.state_dir,
                interval=10.0,
                webhook_timeout=5.0,
                mark_unhealthy_fn=lambda agent_id: lifecycle.heartbeat(agent_id, status="unhealthy"),
                webhook_lookup_fn=_webhook_lookup,
            )
        )

    dlq_thread = threading.Thread(target=_run_dlq_loop, daemon=True, name="dlq-retry")
    dlq_thread.start()

    class Handler(AgentroomHandler):
        room_lifecycle = lifecycle
        room_store = store
        dlq_loop = dlq_event_loop

    httpd = ThreadingHTTPServer((host, port), Handler)
    logger.info(f"agentroom listening on http://{host}:{port}")
    print(f"agentroom listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
        dlq_event_loop.call_soon_threadsafe(dlq_event_loop.stop)
        httpd.shutdown()


class AgentroomHandler(BaseHTTPRequestHandler):
    room_lifecycle: AgentroomLifecycle
    room_store: AgentroomStore
    dlq_loop: asyncio.AbstractEventLoop

    def do_GET(self) -> None:
        try:
            path, query = self._path_query()
            if path == ["health"]:
                self._json({"ok": True})
            elif path == ["metrics"]:
                self._text(metrics.collect(), content_type="text/plain; version=0.0.4; charset=utf-8")
            elif path == ["status"]:
                self._json(self._enhanced_status())
            elif path == ["rooms"]:
                self._json(
                    self.room_lifecycle.discover_rooms(
                        status=query.get("status", ["active"])[0] or None,
                        prefix=query.get("prefix", [None])[0],
                    )
                )
            elif len(path) == 3 and path[0] == "rooms" and path[2] == "messages":
                room_id = unquote(path[1])
                agent_id = query.get("agent", [None])[0]
                unread = query.get("unread", ["false"])[0].lower() == "true"
                mark_read = query.get("mark_read", ["false"])[0].lower() == "true"
                limit = query.get("limit", [None])[0]
                if unread:
                    if not agent_id:
                        raise ValueError("agent query parameter is required for unread reads")
                    messages = self.room_lifecycle.store.list_unread(agent_id, room_id, mark_read=mark_read)
                else:
                    messages = self.room_lifecycle.store.list_messages(room_id, limit=int(limit) if limit else None)
                self._json(messages)
            elif path == ["agents"]:
                self._json(
                    self.room_lifecycle.list_agents(
                        role=query.get("role", [None])[0],
                        capability=query.get("capability", [None])[0],
                        status=query.get("status", [None])[0],
                    )
                )
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        try:
            path, _query = self._path_query()
            body = self._read_json()
            if path == ["rooms"]:
                self._json(
                    self.room_lifecycle.create_room(
                        body["roomId"],
                        topic=body.get("topic"),
                        metadata=body.get("metadata"),
                    ),
                    HTTPStatus.CREATED,
                )
            elif len(path) == 3 and path[0] == "rooms" and path[2] == "messages":
                room_id = unquote(path[1])
                with Timer(metrics.message_append_duration):
                    if body.get("format") == "a2a":
                        result = self.room_lifecycle.post_a2a(
                            room_id,
                            payload=body["payload"],
                            agent_id=body["from"]["agentId"],
                            role=body["from"]["role"],
                            adapter=body["from"]["adapter"],
                            to=body.get("to", []),
                            topic=body.get("topic"),
                        )
                    else:
                        text = body.get("text") or body.get("payload", {}).get("text")
                        result = self.room_lifecycle.post_text(
                            room_id,
                            text=text,
                            agent_id=body["from"]["agentId"],
                            role=body["from"]["role"],
                            adapter=body["from"]["adapter"],
                            to=body.get("to", []),
                            topic=body.get("topic"),
                        )
                metrics.messages_total.inc()
                # Dispatch to webhook subscribers
                self._dispatch_webhooks(result["message"])
                self._json(result, HTTPStatus.CREATED)
            elif len(path) == 3 and path[0] == "rooms" and path[2] == "archive":
                self._json(self.room_lifecycle.archive_room(unquote(path[1])))
            elif len(path) == 3 and path[0] == "rooms" and path[2] == "join":
                self._json(
                    self.room_lifecycle.join_room(
                        unquote(path[1]),
                        body["agentId"],
                        role=body.get("role", "agent"),
                        adapter=body.get("adapter", "unknown"),
                        capabilities=body.get("capabilities", []),
                    )
                )
            elif len(path) == 3 and path[0] == "rooms" and path[2] == "leave":
                self._json(
                    self.room_lifecycle.leave_room(
                        unquote(path[1]),
                        body["agentId"],
                        role=body.get("role", "agent"),
                        adapter=body.get("adapter", "unknown"),
                    )
                )
            elif path == ["agents", "register"]:
                self._json(
                    self.room_lifecycle.register_agent(
                        body["agentId"],
                        role=body["role"],
                        adapter=body["adapter"],
                        capabilities=body.get("capabilities", []),
                        webhook=body.get("webhook"),
                        server=body.get("server"),
                        metadata=body.get("metadata"),
                    ),
                    HTTPStatus.CREATED,
                )
            elif len(path) == 3 and path[0] == "agents" and path[2] == "heartbeat":
                self._json(self.room_lifecycle.heartbeat(unquote(path[1]), status=body.get("status", "online")))
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _dispatch_webhooks(self, message: dict[str, Any]) -> None:
        """Fire-and-forget webhook dispatch in background."""
        if self.dlq_loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            dispatch_after_append(message, self.room_store),
            self.dlq_loop,
        )
        # Don't await — fire and forget

    def _enhanced_status(self) -> dict[str, Any]:
        """Enhanced status with webhook and DLQ stats."""
        base = self.room_lifecycle.status()
        # Update gauge metrics
        metrics.active_rooms.set(base["rooms"]["active"])
        metrics.registered_agents.set(base["agents"]["registered"])
        metrics.healthy_agents.set(base["agents"]["healthy"])
        base["metrics"] = {
            "webhook_deliveries": {
                "success": metrics.webhook_deliveries_total._label_values.get(("success",), 0),
                "failure": metrics.webhook_deliveries_total._label_values.get(("failure",), 0),
            },
            "dlq_pending": base["dlq"]["pending"],
        }
        return base

    def _path_query(self) -> tuple[list[str], dict[str, list[str]]]:
        parsed = urlparse(self.path)
        path = [part for part in parsed.path.split("/") if part]
        return path, parse_qs(parsed.query)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _text(self, payload: str, content_type: str = "text/plain", status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
