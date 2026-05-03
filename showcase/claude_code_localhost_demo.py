#!/usr/bin/env python3
"""Agentroom localhost showcase — multi-port demo with Claude Code agent.

This script demonstrates a full Agentroom coordination loop on localhost
using **two different ports**:

  * Port 8765 — Agentroom central HTTP server (rooms, agents, metrics)
  * Port 9001 — Webhook receiver echo server (shows cross-port delivery)

A "Claude Code" internal agent polls unread messages from the room,
spawns the real ``claude`` CLI to generate responses, and posts them back.

Usage::

    python showcase/claude_code_localhost_demo.py

Requirements::

    pip install -e .          # agentroom package
    The ``claude`` binary must be on PATH and authenticated.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Agentroom imports
# --------------------------------------------------------------------------- #
from agentroom.adapters.base import ConcurrencyPool, ModelCache
from agentroom.adapters.claude_code import ClaudeCodeAdapter
from agentroom.core import AgentroomStore
from agentroom.lifecycle import AgentroomLifecycle
from agentroom.server import AgentroomHandler

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
AGENTROOM_PORT = 8765
WEBHOOK_PORT = 9001
ROOM_ID = "showcase:code-review"
STATE_DIR = Path(__file__).with_name("_demo_state")

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _banner(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _json_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    import urllib.request

    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _json_get(url: str) -> Any:
    import urllib.request

    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


# --------------------------------------------------------------------------- #
# Webhook echo server (port 9001)
# --------------------------------------------------------------------------- #


class WebhookEchoHandler(BaseHTTPRequestHandler):
    """Simple receiver that prints every incoming webhook payload."""

    received: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        WebhookEchoHandler.received.append(body)
        print(
            f"  [WEBHOOK {WEBHOOK_PORT}] -> {body.get('roomId')} | "
            f"from={body.get('from', {}).get('agentId')} | "
            f"format={body.get('format')}"
        )
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ARG002
        return


def start_webhook_server(port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), WebhookEchoHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


# --------------------------------------------------------------------------- #
# Main demo
# --------------------------------------------------------------------------- #


async def run_demo() -> None:
    if not shutil.which("claude"):
        print("ERROR: 'claude' binary not found on PATH. Install Claude Code first.")
        sys.exit(1)

    # Clean slate
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR, ignore_errors=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 1. Spin up Agentroom HTTP server on 8765
    # ------------------------------------------------------------------ #
    _banner("1. Starting Agentroom server")
    store = AgentroomStore(STATE_DIR / "agentroom")
    lifecycle = AgentroomLifecycle(store)

    class Handler(AgentroomHandler):
        room_lifecycle = lifecycle
        room_store = store
        dlq_loop = None  # type: ignore[assignment]

    agentroom_server = ThreadingHTTPServer(("127.0.0.1", AGENTROOM_PORT), Handler)
    threading.Thread(target=agentroom_server.serve_forever, daemon=True).start()
    print(f"   Agentroom listening on http://127.0.0.1:{AGENTROOM_PORT}")
    time.sleep(0.2)

    # ------------------------------------------------------------------ #
    # 2. Spin up webhook echo server on 9001
    # ------------------------------------------------------------------ #
    _banner("2. Starting webhook echo server")
    webhook_server = start_webhook_server(WEBHOOK_PORT)
    print(f"   Webhook receiver listening on http://127.0.0.1:{WEBHOOK_PORT}")

    base = f"http://127.0.0.1:{AGENTROOM_PORT}"

    # ------------------------------------------------------------------ #
    # 3. Register agents
    # ------------------------------------------------------------------ #
    _banner("3. Registering agents")

    human = _json_post(
        f"{base}/agents/register",
        {
            "agentId": "human-dev",
            "role": "developer",
            "adapter": "manual",
            "capabilities": ["python", "review"],
        },
    )
    print(f"   Registered: {human['agentId']} (role={human['role']})")

    claude = _json_post(
        f"{base}/agents/register",
        {
            "agentId": "claude-reviewer",
            "role": "reviewer",
            "adapter": "claude_code",
            "capabilities": ["analysis", "suggestions"],
            "webhook": f"http://127.0.0.1:{WEBHOOK_PORT}/webhook",
        },
    )
    print(f"   Registered: {claude['agentId']} (role={claude['role']}, webhook={claude.get('webhook')})")

    # ------------------------------------------------------------------ #
    # 4. Create room
    # ------------------------------------------------------------------ #
    _banner("4. Creating coordination room")
    room = _json_post(
        f"{base}/rooms",
        {
            "roomId": ROOM_ID,
            "topic": "Code review showcase",
            "metadata": {"project": "agentroom-showcase", "priority": "high"},
        },
    )
    print(f"   Room: {room['roomId']} (status={room['status']})")

    # ------------------------------------------------------------------ #
    # 5. Agents join room
    # ------------------------------------------------------------------ #
    _banner("5. Agents joining room")
    for agent_id in ("human-dev", "claude-reviewer"):
        result = _json_post(
            f"{base}/rooms/{ROOM_ID}/join",
            {
                "agentId": agent_id,
                "role": "developer" if agent_id == "human-dev" else "reviewer",
                "adapter": "manual" if agent_id == "human-dev" else "claude_code",
            },
        )
        print(f"   {agent_id} joined -> rooms={result.get('rooms', [])}")

    # ------------------------------------------------------------------ #
    # 6. Human posts a review request
    # ------------------------------------------------------------------ #
    _banner("6. Human posts a review request")
    msg = _json_post(
        f"{base}/rooms/{ROOM_ID}/messages",
        {
            "format": "plain_text",
            "from": {"agentId": "human-dev", "role": "developer", "adapter": "manual"},
            "text": (
                "Please review this function:\n\n"
                "def divide(a, b):\n"
                "    return a / b\n\n"
                "It works for happy-path but I'm worried about edge cases."
            ),
        },
    )
    print(f"   Posted message id={msg['message']['id']}")

    # ------------------------------------------------------------------ #
    # 7. Claude agent polls unread and responds
    # ------------------------------------------------------------------ #
    _banner("7. Claude agent polls & responds")

    adapter = ClaudeCodeAdapter(
        agent_id="claude-reviewer",
        role="reviewer",
        cache=ModelCache(),
        pool=ConcurrencyPool(max_concurrent=1),
    )

    # Poll unread messages for claude-reviewer
    unread = store.list_unread("claude-reviewer", ROOM_ID, mark_read=True)
    print(f"   Unread messages for claude-reviewer: {len(unread)}")

    if unread:
        responses = await adapter.process(ROOM_ID, unread)
        for resp in responses:
            text = resp.get("text", "")
            if text:
                result = lifecycle.post_text(
                    ROOM_ID,
                    text=text,
                    agent_id="claude-reviewer",
                    role="reviewer",
                    adapter="claude_code",
                )
                print(f"   Claude responded -> message id={result['message']['id']}")
                print(f"   Response preview: {text[:200].replace(chr(10), ' ')}")

    # Give webhooks a moment to fire
    time.sleep(0.5)

    # ------------------------------------------------------------------ #
    # 8. Display final room transcript
    # ------------------------------------------------------------------ #
    _banner("8. Room transcript")
    messages = _json_get(f"{base}/rooms/{ROOM_ID}/messages")
    for m in messages:
        sender = m.get("from", {}).get("agentId", "?")
        fmt = m.get("format", "?")
        payload = m.get("payload", {})
        text = payload.get("text", payload.get("summary", str(payload)[:80]))
        print(f"   [{fmt}] {sender}: {text[:120].replace(chr(10), ' ')}")

    # ------------------------------------------------------------------ #
    # 9. Status & metrics
    # ------------------------------------------------------------------ #
    _banner("9. Status & metrics")
    status = _json_get(f"{base}/status")
    print(f"   Active rooms : {status['rooms']['active']}")
    print(f"   Registered   : {status['agents']['registered']}")
    print(f"   Healthy      : {status['agents']['healthy']}")
    print(f"   Webhook OK   : {status['metrics']['webhook_deliveries']['success']}")
    print(f"   Webhook FAIL : {status['metrics']['webhook_deliveries']['failure']}")

    import urllib.request

    with urllib.request.urlopen(f"{base}/metrics") as resp:
        metrics_text = resp.read().decode()
    for line in metrics_text.splitlines():
        if line.startswith("agentroom_") and not line.startswith("#"):
            print(f"   {line}")

    # ------------------------------------------------------------------ #
    # 10. Webhook delivery log
    # ------------------------------------------------------------------ #
    _banner("10. Webhook deliveries (port 9001)")
    if WebhookEchoHandler.received:
        for wh in WebhookEchoHandler.received:
            sender = wh.get("from", {}).get("agentId", "?")
            print(f"   -> from={sender} room={wh.get('roomId')}")
    else:
        print("   No webhooks received (expected when dlq_loop is None in demo).")

    # ------------------------------------------------------------------ #
    # Cleanup
    # ------------------------------------------------------------------ #
    _banner("Cleanup")
    agentroom_server.shutdown()
    webhook_server.shutdown()
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR, ignore_errors=True)
    print("   Demo complete.\n")


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def main() -> int:
    try:
        asyncio.run(run_demo())
    except Exception as exc:
        print(f"Demo failed: {exc}")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
