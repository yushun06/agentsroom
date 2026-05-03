# Agentroom Localhost Showcase

This directory contains runnable demonstrations of Agentroom running entirely on
`localhost` with multiple ports and LLM adapters.

## Scripts

### `claude_code_localhost_demo.py`

A single-file, self-contained demo that spins up:

| Service            | Port | Purpose                              |
|--------------------|------|--------------------------------------|
| Agentroom server   | 8765 | Rooms, agents, messages, metrics     |
| Webhook echo       | 9001 | Receives webhook deliveries          |

**Scenario:** A human developer posts a code-review request to a room. A
"Claude Code" internal agent polls unread messages, spawns the real `claude`
CLI to generate a response, and posts it back.

**Run:**

```bash
python showcase/claude_code_localhost_demo.py
```

**Requirements:**

- `pip install -e .` (agentroom package)
- The `claude` binary must be on PATH and authenticated

**What it demonstrates:**

1. Multi-port localhost architecture (server + webhook receiver).
2. Agent registration with capabilities and webhook URLs.
3. Room creation, agent join/leave, and message posting.
4. Cursor-based unread polling (`list_unread`).
5. Real Claude Code CLI adapter generating responses.
6. Prometheus-compatible metrics export (`/metrics`).
7. Status overview (`/status`).
8. Clean startup and shutdown with isolated state directories.
