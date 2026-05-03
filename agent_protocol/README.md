# Agent Working Environment

Welcome to the `work/` directory. This is the centralized hub for all agent coordination, tracking, and artifact management. 
Agentroom remains the real-time event stream, but **Markdown files are the shared workspace memory.**

## Getting Started
**Before taking any action**, you MUST read the [Agent Working Protocol](protocol.md). This document defines the lifecycle, alignment gates, and strict coordination rules for this repository.

## Key Directories & Artifact Types
*   `journeys/`: `JRN-*` files define user goals, flows, and acceptance criteria.
*   `designs/`: `DES-*` files describe technical architecture and rollout plans.
*   `tasks/`: `TASK-*` files are executable work plans.
*   `checklists/`: `CHK-*` files capture validation procedures and evidence.
*   `todos/`: `TODO-*` files hold deferred work to prevent blocking current changes.
*   `decisions/`: `ADR-*` files record durable architectural choices.
*   `changes/`: `CHG-*` files are manifests binding code edits to tasks.
*   `reviews/`: `REV-*` files capture code review findings and disposition.

> **Templates for all artifacts can be found in `templates/`.**

## Agent Responsibilities

| Role | Responsibilities |
|---|---|
| **Planner Agent** | Creates journeys, designs, task breakdowns, and decision records. Owns scope clarity. |
| **Worker Agent** | Claims task files, edits code, maintains change files, and records verification commands. |
| **Test Agent** | Creates and executes checklist files. Updates task/change artifacts with evidence/gaps. |
| **Review Agent** | Creates review files, records findings, verifies consistency links, and approves/rejects. |
| **Docs Agent** | Updates user-facing and architecture docs when behavior or APIs change. |
| **Supervisor Agent** | Maintains `index.md`, detects stale artifacts, reassigns blocked tasks, and closes work. |

Remember the golden rule: **Agents do not coordinate through private memory. Agents coordinate by keeping shared markdown artifacts current, specific, and resumable.**
