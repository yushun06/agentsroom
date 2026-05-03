"""Command line interface for Agentroom."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from .adapters.base import ConcurrencyPool, ModelCache
from .core import AgentroomStore
from .lifecycle import AgentroomLifecycle
from .observability.logger import setup_logging
from .server import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentctl")
    parser.add_argument("--state-dir", default=".state/agentroom")
    sub = parser.add_subparsers(dest="resource", required=True)

    rooms = sub.add_parser("rooms")
    rooms_sub = rooms.add_subparsers(dest="action", required=True)
    discover = rooms_sub.add_parser("discover")
    discover.add_argument("--status", default="active")
    discover.add_argument("--prefix")

    room = sub.add_parser("room")
    room_sub = room.add_subparsers(dest="action", required=True)
    create = room_sub.add_parser("create")
    create.add_argument("room_id")
    create.add_argument("--topic")
    archive = room_sub.add_parser("archive")
    archive.add_argument("room_id")
    join = room_sub.add_parser("join")
    join.add_argument("room_id")
    join.add_argument("--agent", required=True)
    join.add_argument("--role", default="agent")
    join.add_argument("--adapter", default="unknown")
    join.add_argument("--capabilities", default="")
    leave = room_sub.add_parser("leave")
    leave.add_argument("room_id")
    leave.add_argument("--agent", required=True)
    leave.add_argument("--role", default="agent")
    leave.add_argument("--adapter", default="unknown")
    post = room_sub.add_parser("post")
    post.add_argument("room_id")
    post.add_argument("--agent", default="anonymous")
    post.add_argument("--role", default="agent")
    post.add_argument("--adapter", default="unknown")
    post.add_argument("--text")
    post.add_argument("--a2a")
    post.add_argument("--to", action="append", default=[])
    post.add_argument("--topic")
    list_cmd = room_sub.add_parser("list")
    list_cmd.add_argument("room_id")
    list_cmd.add_argument("--agent")
    list_cmd.add_argument("--unread-only", action="store_true")
    list_cmd.add_argument("--mark-read", action="store_true")
    list_cmd.add_argument("--limit", type=int)
    watch = room_sub.add_parser("watch")
    watch.add_argument("room_id")
    watch.add_argument("--agent", required=True)
    watch.add_argument("--interval", type=float, default=1.0)

    agents = sub.add_parser("agents")
    agents_sub = agents.add_subparsers(dest="action", required=True)
    register = agents_sub.add_parser("register")
    register.add_argument("--agent", required=True)
    register.add_argument("--role", required=True)
    register.add_argument("--adapter", required=True)
    register.add_argument("--capabilities", default="")
    register.add_argument("--webhook")
    register.add_argument("--server")
    list_agents = agents_sub.add_parser("list")
    list_agents.add_argument("--role")
    list_agents.add_argument("--capability")
    list_agents.add_argument("--status")
    heartbeat = agents_sub.add_parser("heartbeat")
    heartbeat.add_argument("--agent", required=True)
    heartbeat.add_argument("--status", default="online")

    agent = sub.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="action", required=True)
    run_cmd = agent_sub.add_parser("run")
    run_cmd.add_argument("--agent", required=True)
    run_cmd.add_argument("--adapter", required=True, choices=["codex", "claude_code", "gemini"])
    run_cmd.add_argument("--room", required=True)
    run_cmd.add_argument("--role", default="agent")
    run_cmd.add_argument("--interval", type=float, default=2.0)
    run_cmd.add_argument("--max-concurrent", type=int, default=3)
    run_cmd.add_argument("--log-level", default="INFO")

    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--log-level", default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resource == "agent" and args.action == "run":
        return asyncio.run(_run_adapter(args))
    lifecycle = AgentroomLifecycle(AgentroomStore(args.state_dir))
    try:
        result = dispatch(args, lifecycle)
    except Exception as exc:
        print(f"agentctl: {exc}", file=sys.stderr)
        return 1
    if result is not None:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def dispatch(args: argparse.Namespace, lifecycle: AgentroomLifecycle) -> Any:
    if args.resource == "rooms" and args.action == "discover":
        return lifecycle.discover_rooms(status=args.status, prefix=args.prefix)
    if args.resource == "room":
        return _dispatch_room(args, lifecycle)
    if args.resource == "agents":
        return _dispatch_agents(args, lifecycle)
    if args.resource == "serve":
        serve(host=args.host, port=args.port, state_dir=args.state_dir, log_level=args.log_level)
        return None
    raise ValueError("unsupported command")


def _dispatch_room(args: argparse.Namespace, lifecycle: AgentroomLifecycle) -> Any:
    if args.action == "create":
        return lifecycle.create_room(args.room_id, topic=args.topic)
    if args.action == "archive":
        return lifecycle.archive_room(args.room_id)
    if args.action == "join":
        return lifecycle.join_room(
            args.room_id,
            args.agent,
            role=args.role,
            adapter=args.adapter,
            capabilities=_csv(args.capabilities),
        )
    if args.action == "leave":
        return lifecycle.leave_room(args.room_id, args.agent, role=args.role, adapter=args.adapter)
    if args.action == "post":
        targets = [{"agentId": item} for item in args.to]
        if args.a2a:
            payload = json.loads(Path(args.a2a).read_text(encoding="utf-8"))
            return lifecycle.post_a2a(
                args.room_id,
                payload=payload,
                agent_id=args.agent,
                role=args.role,
                adapter=args.adapter,
                to=targets,
                topic=args.topic,
            )
        if args.text is None:
            raise ValueError("room post requires --text or --a2a")
        return lifecycle.post_text(
            args.room_id,
            text=args.text,
            agent_id=args.agent,
            role=args.role,
            adapter=args.adapter,
            to=targets,
            topic=args.topic,
        )
    if args.action == "list":
        if args.unread_only:
            if not args.agent:
                raise ValueError("--agent is required with --unread-only")
            return lifecycle.store.list_unread(args.agent, args.room_id, mark_read=args.mark_read)
        return lifecycle.store.list_messages(args.room_id, limit=args.limit)
    if args.action == "watch":
        seen: set[str] = set()
        while True:
            for message in lifecycle.store.list_unread(args.agent, args.room_id, mark_read=True):
                if message["id"] not in seen:
                    print(json.dumps(message, sort_keys=True), flush=True)
                    seen.add(message["id"])
            time.sleep(args.interval)
    raise ValueError("unsupported room command")


def _dispatch_agents(args: argparse.Namespace, lifecycle: AgentroomLifecycle) -> Any:
    if args.action == "register":
        return lifecycle.register_agent(
            args.agent,
            role=args.role,
            adapter=args.adapter,
            capabilities=_csv(args.capabilities),
            webhook=args.webhook,
            server=args.server,
        )
    if args.action == "list":
        return lifecycle.list_agents(role=args.role, capability=args.capability, status=args.status)
    if args.action == "heartbeat":
        return lifecycle.heartbeat(args.agent, status=args.status)
    raise ValueError("unsupported agents command")


async def _run_adapter(args: argparse.Namespace) -> int:
    """Run an adapter that polls a room and processes messages through an LLM."""
    setup_logging(args.log_level)
    store = AgentroomStore(args.state_dir)
    lifecycle = AgentroomLifecycle(store)

    # Ensure agent is registered
    agents = lifecycle.list_agents()
    if not any(a["agentId"] == args.agent for a in agents):
        lifecycle.register_agent(args.agent, role=args.role, adapter=args.adapter)

    # Ensure agent is in the room
    presence_path = store.presence_dir / f"{args.agent}.json"
    presence = store.read_json(presence_path, {"rooms": []})
    if args.room not in presence.get("rooms", []):
        lifecycle.join_room(args.room, args.agent, role=args.role, adapter=args.adapter)

    # Create adapter
    cache = ModelCache()
    pool = ConcurrencyPool(max_concurrent=args.max_concurrent)
    adapter_cls = _get_adapter_class(args.adapter)
    adapter = adapter_cls(args.agent, args.role, cache, pool)

    print(f"agentctl: running {args.adapter} adapter for {args.agent} in room {args.room}")
    try:
        while True:
            messages = store.list_unread(args.agent, args.room, mark_read=True)
            if messages:
                responses = await adapter.process(args.room, messages)
                for resp in responses:
                    text = resp.get("text", "")
                    if text:
                        lifecycle.post_text(
                            args.room,
                            text=text,
                            agent_id=args.agent,
                            role=args.role,
                            adapter=args.adapter,
                        )
            await asyncio.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nagentctl: adapter stopped")
        return 0


def _get_adapter_class(name: str) -> type:
    if name == "codex":
        from .adapters.codex import CodexAdapter

        return CodexAdapter
    if name == "claude_code":
        from .adapters.claude_code import ClaudeCodeAdapter

        return ClaudeCodeAdapter
    if name == "gemini":
        from .adapters.gemini import GeminiAdapter

        return GeminiAdapter
    raise ValueError(f"unknown adapter: {name}")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
