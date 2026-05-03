# Codex Memory

This repository uses `agent_protocol/` as the shared working memory for all
agent coordination. Agentroom is the real-time event stream, but markdown
artifacts are the durable source of truth.

## Required Reading

Before taking any action, read:

1. `agent_protocol/README.md`
2. `agent_protocol/protocol.md`

The protocol defines lifecycle states, alignment gates, ownership rules,
handoff requirements, and completion criteria. Treat it as binding.

## Core Rule

Agents do not coordinate through private memory. Agents coordinate by keeping
shared markdown artifacts current, specific, and resumable.

## Working Directories

Use `agent_protocol/work/` for coordination artifacts:

- `journeys/`: `JRN-*` files for user goals, flows, and acceptance criteria.
- `designs/`: `DES-*` files for technical architecture and rollout plans.
- `tasks/`: `TASK-*` files for executable work plans.
- `checklists/`: `CHK-*` files for validation procedures and evidence.
- `todos/`: `TODO-*` files for deferred work.
- `decisions/`: `ADR-*` files for durable architectural choices.
- `changes/`: `CHG-*` files binding code edits to tasks.
- `reviews/`: `REV-*` files for review findings and disposition.

Templates live in `agent_protocol/work/templates/`.

## Operating Rules

- Write intent before acting.
- Read linked artifacts before editing.
- Check active ownership in `agent_protocol/ownership.md`.
- Do not edit files owned by another active task without coordination.
- Update ownership and task artifacts before editing unlisted files.
- Keep intent, state, and evidence separate.
- Preserve coordination history where practical.
- Make non-changes explicit.

## Lifecycle Expectations

Use the lifecycle states from `agent_protocol/protocol.md`:

- `idle`
- `discovering`
- `claiming`
- `working`
- `blocked`
- `waiting_for_review`
- `fixing_review`
- `handoff`
- `done`
- `stale`

Any unfinished work must leave a markdown handoff that includes current state,
touched files, commands run, blockers, and the next action.

## Completion Criteria

Do not close work until:

- Changed files are listed.
- Verification commands and evidence are recorded.
- Checklist items are complete or deferred into TODO artifacts.
- Review is approved or explicitly not required.
- Agentroom status and markdown status agree.

