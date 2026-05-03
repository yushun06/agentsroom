# Agentroom

File-backed coordination rooms for distributed AI agents — with webhook dispatch, DLQ retry, LLM adapters, and Prometheus metrics.

## What is Agentroom?

Agentroom is a lightweight, file-backed coordination hub for distributed AI agents. It provides persistent rooms where agents can register, discover each other, exchange messages, and coordinate tasks — all without external databases or message brokers.

**Key design principles:**

- **File-backed durability** — All state lives on disk (JSONL segments, JSON indexes, cursor files). No database required.
- **HTTP API + CLI** — Use `agentctl` locally or run the central HTTP server for remote coordination.
- **Cursor-based polling** — Agents poll unread messages efficiently without re-reading history.
- **Webhook fan-out** — Cross-server message delivery with automatic retry and dead-letter queues.
- **Zero external dependencies** — Pure Python 3.11+ standard library.

## Features

- **Rooms** — Append-only message streams with automatic segment rotation (10 MB / 50K messages)
- **Agent lifecycle** — Register, join/leave rooms, heartbeat health status
- **Discovery** — Query active rooms and agents by role, capability, or status
- **Message formats** — `plain_text` and structured `a2a` (Agent-to-Agent) payloads
- **Unread cursors** — Per-agent cursor tracking for efficient polling
- **Webhooks** — Async fan-out delivery with configurable timeouts
- **Dead Letter Queue** — Exponential backoff retry; marks exhausted agents `unhealthy`
- **LLM Adapters** — Built-in adapters for `codex`, `claude_code`, and `gemini`
- **Observability** — Structured JSON logging and Prometheus-compatible metrics

## Installation

```bash
pip install -e .
```

Requires Python >= 3.11. The CLI entry point is `agentctl`.

**Development dependencies:**

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Start the server

```bash
agentctl serve --host 127.0.0.1 --port 8765
```

### 2. Create a room

```bash
agentctl room create project:workspace --topic "Team coordination"
```

### 3. Register agents

```bash
agentctl agents register --agent worker-a --role worker --adapter codex
agentctl agents register --agent reviewer-b --role reviewer --adapter claude_code
```

### 4. Join the room

```bash
agentctl room join project:workspace --agent worker-a --role worker --adapter codex
agentctl room join project:workspace --agent reviewer-b --role reviewer --adapter claude_code
```

### 5. Post a message

```bash
agentctl room post project:workspace --text "Ready for review" --to reviewer-b
```

### 6. Poll unread messages

```bash
agentctl room list project:workspace --agent reviewer-b --unread-only
```

### 7. Run an adapter agent

```bash
agentctl agent run --agent reviewer-b --adapter claude_code --room project:workspace
```

## CLI Reference

### Rooms

| Command | Description |
|---|---|
| `agentctl rooms discover [--status active] [--prefix ...]` | List rooms |
| `agentctl room create <id> --topic "..."` | Create a room |
| `agentctl room archive <id>` | Archive a room |
| `agentctl room join <id> --agent <id> --role <role>` | Join a room |
| `agentctl room leave <id> --agent <id>` | Leave a room |
| `agentctl room post <id> --text "..." [--to ...]` | Post a message |
| `agentctl room list <id> [--agent <id> --unread-only]` | List messages |
| `agentctl room watch <id> --agent <id> --interval 1.0` | Stream messages |

### Agents

| Command | Description |
|---|---|
| `agentctl agents register --agent <id> --role <role> --adapter <name>` | Register an agent |
| `agentctl agents list [--role ...] [--capability ...]` | List agents |
| `agentctl agents heartbeat --agent <id> --status <status>` | Send heartbeat |

### Server

| Command | Description |
|---|---|
| `agentctl serve --host 127.0.0.1 --port 8765` | Start HTTP server |

## HTTP API

### GET Endpoints

| Path | Description |
|---|---|
| `/health` | Health check |
| `/status` | Room/agent counts, DLQ stats, metrics |
| `/metrics` | Prometheus-format metrics |
| `/rooms?status=active&prefix=...` | Discover rooms |
| `/rooms/<id>/messages?agent=...&unread=true&mark_read=true` | List messages |
| `/agents?role=...&capability=...&status=...` | List agents |

### POST Endpoints

| Path | Description |
|---|---|
| `/rooms` | Create room |
| `/rooms/<id>/messages` | Post message |
| `/rooms/<id>/archive` | Archive room |
| `/rooms/<id>/join` | Join room |
| `/rooms/<id>/leave` | Leave room |
| `/agents/register` | Register agent |
| `/agents/<id>/heartbeat` | Heartbeat |

### Message POST Body

```json
{
  "format": "plain_text",
  "from": {"agentId": "worker-a", "role": "worker", "adapter": "codex"},
  "text": "Hello from worker-a",
  "to": []
}
```

A2A format:

```json
{
  "format": "a2a",
  "from": {"agentId": "worker-a", "role": "worker", "adapter": "codex"},
  "payload": {
    "schema": "agentroom.a2a.v1",
    "type": "task.update",
    "intent": "inform",
    "summary": "Task completed"
  }
}
```

## Architecture

```
agentroom/
  core.py            # File-backed storage, locking, segment rotation, cursors
  schemas.py         # Envelope validation, A2A schema
  lifecycle.py       # Room/agent CRUD, join/leave, heartbeat
  cli.py             # agentctl CLI
  server.py          # HTTP REST API
  adapters/
    base.py          # BaseAdapter, ModelCache, ConcurrencyPool, PromptCompiler
    codex.py         # Codex CLI adapter
    claude_code.py   # Claude Code CLI adapter
    gemini.py        # Gemini CLI adapter
  delivery/
    webhook.py       # Async fan-out delivery
    dlq.py           # Dead Letter Queue with retry loop
    poller.py        # Cursor-based polling helper
  observability/
    logger.py        # Structured JSON logging
    metrics.py       # Prometheus-compatible metrics
```

### State Storage

```
.state/agentroom/
  index.json         # Room catalog
  registry.json      # Agent catalog
  rooms/             # <room-id>.<segment>.jsonl
  archive/           # Compressed archived segments
  cursors/           # Per-agent read cursors
  presence/          # Agent heartbeat + room membership
  dlq/               # Failed webhook payloads
```

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

| File | Coverage |
|---|---|
| `tests/test_agentroom.py` | Unit tests: store, lifecycle, DLQ, webhooks, metrics, logging, adapters |
| `tests/test_http_integration.py` | HTTP server integration tests |
| `tests/test_e2e_localhost.py` | End-to-end multi-agent lifecycle |

Run the full CI pipeline locally:

```bash
make check
```

## Showcase

`showcase/claude_code_localhost_demo.py` demonstrates a complete coordination loop:

- Agentroom server on port 8765 + webhook echo server on port 9001
- Human developer posts a code review request
- Claude Code agent polls unread messages, invokes the real `claude` CLI, and posts a response
- Displays transcript, status, and Prometheus metrics

```bash
python showcase/claude_code_localhost_demo.py
```

Requires the `claude` binary on PATH.

## Development

**Lint:** `make lint` (ruff)

**Format:** `make format` (ruff)

**Test:** `make test` (pytest)

**Full check:** `make check` (lint + format-check + test + review-check)

## Agent Coordination

This repository uses `agent_protocol/` as shared working memory for agent coordination. See:

- `agent_protocol/protocol.md` — Lifecycle states, alignment gates, ownership rules
- `agent_protocol/coding-rules.md` — Binding coding standards for all agents
- `agent_protocol/review-rules.md` — Binding review standards for all agents

## License

MIT
