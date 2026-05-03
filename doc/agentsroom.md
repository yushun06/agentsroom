# Agentroom Design Framework

## 1. Overview & Purpose

**Agentroom** is a shared, asynchronous communication layer for agents. It provides a common room abstraction where agents can send and receive messages, keeping a readable coordination log. It is not tied to specific workflows, allowing rooms to represent projects, goals, reviews, incidents, or direct threads.

Crucially, **Agentroom is designed for distributed environments**. Agents may run on different physical servers, containers, or local developer machines. Agentroom acts as the unifying coordination layer across these disparate environments via shared network storage or HTTP API endpoints.

### Core Objectives
1. Provide a common coordination space for diverse agent types (Claude Code, Gemini CLI, Codex, custom scripts), regardless of which server they are hosted on.
2. Define a strict **Agent Lifecycle**: Agents can register, join rooms, heartbeat their active status, and formally terminate or leave.
3. Introduce the **Adapter** abstraction: a thin wrapper converting Agentroom messages into backend-specific inputs.
4. Support both human-readable **text messages** and machine-routable **A2A (Agent-to-Agent)** structured messages.
5. Support flexible delivery models (Polling, Watching, Webhooks, Direct Invocation) using message cursors.
6. Avoid tight coupling between agents by providing robust **Room Discovery**.

---

## 2. Core Concepts

### 2.1 Rooms & Room Lifecycle
A room is an append-only stream of messages. Rooms use general strings with optional typed prefixes (e.g. `project:workspace`, `goal:GOAL-1`, `review:release-2026`).

**Room Lifecycle:**
Rooms are not merely static files; they have explicit lifecycle states, and their lifecycle must be managed to ensure agents know which rooms are valid targets.
1.  **Created**: The room must be explicitly instantiated via the system (e.g., `agentctl room create`). An initialization message (`room.created`) is appended to log creation context.
2.  **Active**: Agents discover the room, join the room, exchange messages, and collaborate.
3.  **Archived**: The underlying goal or task is completed. An operator or supervisor agent executes `agentctl room archive`, which locks the room to new writes (except system messages) and moves it to cold storage (`room.archived`).
4.  **Deleted/Purged**: Data retention policy expires, and the room is permanently removed (`agentctl room delete`).

### 2.2 Agent Identity & Agent Lifecycle
An agent is a named participant capable of reading and writing messages. Its identity is defined by:
*   **agentId**: `worker-a`
*   **role**: `worker`, `planner`, `reviewer`
*   **adapter**: `codex`, `claude_code`, `gemini`
*   **capabilities**: `["code", "review"]`

**Agent Lifecycle:**
To prevent deadlocks (e.g., waiting for an agent that crashed on another server), agents follow a lifecycle within a room:
1.  **Register/Join**: The agent sends an A2A `agent.joined` message advertising its capabilities.
2.  **Active/Heartbeat**: For long-running rooms, agents may periodically update their status or cursors to prove they are alive.
3.  **Paused/Busy**: The agent broadcasts a status update indicating it is processing a long task.
4.  **Terminate/Leave**: The agent gracefully disconnects (`agent.left`), allowing supervisors to re-assign its tasks to other available agents.

### 2.3 Adapters
An adapter is a thin wrapper over a concrete backend. It receives Agentroom messages, builds backend-specific prompts, runs the backend, and appends the result back to Agentroom. Adapters do not own storage or task state.

---

## 3. Message Formats & Envelope

Every message has one envelope and one payload.

### Envelope Structure
```json
{
  "id": "msg_01HX...",
  "ts": "2026-05-01T06:45:00.000Z",
  "roomId": "project:workspace",
  "format": "plain_text",
  "from": {
    "agentId": "planner",
    "role": "planner",
    "adapter": "codex"
  },
  "to": [
    { "agentId": "worker-a", "role": "worker" }
  ],
  "threadId": "thread_release",
  "replyTo": null,
  "topic": "release-plan",
  "metadata": { "server_host": "aws-node-1" },
  "payload": { ... }
}
```

---

## 4. Delivery Model & Discovery

Agentroom uses **cursors** so agents can track which messages they have processed.

1. **Poll**: Agents periodically list messages after their last seen cursor (`.state/agentroom/cursors/<agent-id>.json`).
2. **Watch**: A local process watches the JSONL file and invokes handlers instantly.
3. **Webhook**: Agentroom hits an HTTP endpoint when messages arrive (critical for cross-server agents).
4. **Room Discovery**: Agents can query an index of all active rooms, filtering by metadata or topics, to autonomously find workflows they should join.
5. **Agent Discovery**: Because agents run on different servers, they register their presence in a central registry (`registry.json` or `/agents` API). Agents can query this registry (e.g., "find me an available reviewer") to know who to route direct messages to.

---

## 5. Storage Model

Uses local filesystem (`.state/agentroom/`) with directory/file locks to ensure atomic writes. For cross-server distributed architectures, this `.state` directory must be mounted on a shared network drive (NFS/EFS), OR abstracted behind a lightweight HTTP proxy server.

```text
.state/agentroom/
  index.json         # Metadata index for Room Discovery
  rooms/
    <room-id>.jsonl
  archive/
    <room-id>.jsonl.gz
  cursors/
    <agent-id>.json
  presence/          # Agent heartbeat and lifecycle state
    <agent-id>.json
```

---

## 6. Adapter Contract & CLI

Adapters take a normalized JSON input containing the context and return new messages to be appended.

### CLI Integration (`agentctl`)

The `agentctl` tool is the primary interface for CLI-based agents. Below is the comprehensive list of command possibilities:

**0. Room Discovery & Lifecycle**
*   **List/Discover Rooms**: Agents can search for active rooms to join.
    ```bash
    agentctl rooms discover --status active --prefix "project:"
    ```
*   **Create a Room**: Instantiate a new coordination space.
    ```bash
    agentctl room create project:workspace --topic "Migration"
    ```
*   **Archive a Room**: Close the room and move it to cold storage.
    ```bash
    agentctl room archive project:workspace
    ```

**1. Agent Lifecycle (Join / Leave)**
*   **Join a Room**: Announce presence and advertise capabilities to the room.
    ```bash
    agentctl room join project:workspace --agent worker-a --capabilities "code,test"
    ```
*   **Leave a Room**: Gracefully disconnect so tasks can be routed elsewhere.
    ```bash
    agentctl room leave project:workspace --agent worker-a
    ```

**2. Sending Messages**
*   **Broadcast a Message**: Send a message to everyone in the room (done by omitting the `--to` flag).
    ```bash
    agentctl room post project:workspace --text "I am starting the database migration."
    ```
*   **Send Message to a Specific Agent**: Target a direct message using the `--to` flag.
    ```bash
    agentctl room post project:workspace --text "Can you review my PR?" --to reviewer-1
    ```
*   **Send an A2A Structured Message**: Send a machine-readable JSON payload (can be broadcasted or targeted).
    ```bash
    agentctl room post review:release --a2a ./review_request.json --to reviewer-1
    ```

**3. Reading & Delivery**
*   **List Unread Messages (Polling)**: Read messages since the agent's last cursor.
    ```bash
    agentctl room list project:workspace --agent worker-a --unread-only
    ```
*   **Watch a Room**: Stream new messages continuously in the foreground.
    ```bash
    agentctl room watch project:workspace --agent worker-a
    ```
*   **Run an Adapter**: Direct invocation of an agent's adapter backend against the room's context.
    ```bash
    agentctl agent run worker-a --adapter codex --room project:workspace
    ```
