---
id: TODO-0001
type: todo
status: done
owner: backlog
source_task: TASK-0001
related_journeys: []
related_files:
  - agentroom/delivery/
  - agentroom/adapters/
  - agentroom/server.py
  - agentroom/observability/
updated: 2026-05-03
---

# TODO-0001 Production Agentroom Features

## Context
The initial implementation focused on the central file-backed room lifecycle, CLI, schema validation, basic HTTP API, and adapter primitives.

## Why Deferred
The design included production-scale behavior that needed separate implementation and integration testing.

## Completed Work
- [x] Implement persistent webhook subscriptions and asynchronous dispatcher integration after message append.
- [x] Implement DLQ retry loop with exponential backoff and unhealthy agent marking.
- [x] Add concrete Codex, Claude Code, and Gemini adapter runners.
- [x] Add Prometheus metrics and structured JSON logging.
- [x] Add HTTP integration tests and deployment docs.

## Revisit Trigger
No longer needed — all items implemented.
