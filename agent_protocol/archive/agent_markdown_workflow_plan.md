# Markdown Workflow Plan for Fully Automated Coding Agents

## 1. Goal

Fully automated coding agents need durable, human-readable work artifacts in addition to Agentroom's append-only coordination messages. Agentroom records communication. Markdown workflow files record decisions, designs, task state, verification evidence, and future work in forms that agents and humans can inspect, diff, review, and resume.

The goal is to make every code change traceable to:

1. A user journey or software goal.
2. A design or implementation note.
3. An active task list.
4. A verification record.
5. A consistency check against related files and plans.

This plan defines the markdown file system, required schemas, agent behaviors, and rollout steps.

---

## 2. Core Principle

Markdown files are not loose notes. They are structured operational artifacts with stable headings, frontmatter, ownership, status fields, and cross-links.

Agentroom remains the event stream. Markdown is the shared workspace memory:

| Layer | Purpose | Source of Truth |
|---|---|---|
| Agentroom room messages | Real-time communication, routing, requests, status updates | `.state/agentroom/rooms/*.jsonl` |
| Markdown workflow files | Plans, decisions, requirements, tasks, TODOs, verification | Repository `work/` or `doc/` files |
| Code/test/config files | Product implementation | Repository source tree |
| Consistency index | Links between markdown artifacts and changed files | Generated manifest |

---

## 3. Proposed Directory Structure

Use a repo-local `work/` directory for active automation state. Keep product documentation in `doc/`.

```text
work/
├── README.md
├── index.md
├── journeys/
│   └── JRN-0001-user-login.md
├── designs/
│   └── DES-0001-auth-flow.md
├── tasks/
│   └── TASK-0001-implement-login.md
├── checklists/
│   └── CHK-0001-login-verification.md
├── todos/
│   └── TODO-0001-auth-followups.md
├── decisions/
│   └── ADR-0001-session-storage.md
├── changes/
│   └── CHG-0001-login-files.md
├── reviews/
│   └── REV-0001-login-review.md
└── generated/
    ├── consistency-index.json
    ├── artifact-graph.md
    └── stale-artifacts.md
```

For small repositories, `work/` can be replaced by `.agents/work/` if the team wants to keep agent artifacts separate from user-facing docs.

---

## 4. Markdown Artifact Types

### 4.1 Journey Files

Journey files define what the software must support from the user's perspective.

Path: `work/journeys/JRN-####-short-name.md`

Required sections:

```markdown
---
id: JRN-0001
type: journey
status: proposed | active | implemented | deprecated
owner: planner
related_designs: []
related_tasks: []
related_files: []
updated: 2026-05-02
---

# JRN-0001 Short Name

## User
## Goal
## Trigger
## Main Flow
## Alternate Flows
## Failure Flows
## Acceptance Criteria
## Dependencies
## Open Questions
```

Use journeys for product workflows such as onboarding, editing a document, running a build, reviewing a pull request, recovering from failed tests, or deploying a release.

### 4.2 Design Files

Design files describe how the implementation will satisfy one or more journeys.

Path: `work/designs/DES-####-short-name.md`

Required sections:

```markdown
---
id: DES-0001
type: design
status: draft | approved | implemented | superseded
owner: planner
related_journeys: []
related_tasks: []
related_decisions: []
related_files: []
updated: 2026-05-02
---

# DES-0001 Short Name

## Problem
## Goals
## Non-Goals
## Current System
## Proposed Design
## Data Model
## Interfaces
## Consistency Requirements
## Test Strategy
## Rollout Plan
## Risks
## Open Questions
```

### 4.3 Task Files

Task files are executable work plans for agents.

Path: `work/tasks/TASK-####-short-name.md`

Required sections:

```markdown
---
id: TASK-0001
type: task
status: todo | in_progress | blocked | review | done
owner: worker-a
priority: P0 | P1 | P2 | P3
related_journeys: []
related_designs: []
related_changes: []
related_reviews: []
related_files: []
updated: 2026-05-02
---

# TASK-0001 Short Name

## Objective
## Scope
## Out of Scope
## Plan
- [ ] Step 1
- [ ] Step 2

## Files Expected To Change
## Consistency Checks
## Verification
## Result
## Blockers
## Follow-Up TODOs
```

### 4.4 Checklist Files

Checklist files capture reusable or task-specific validation procedures.

Path: `work/checklists/CHK-####-short-name.md`

Required sections:

```markdown
---
id: CHK-0001
type: checklist
status: active | retired
owner: reviewer
related_tasks: []
related_files: []
updated: 2026-05-02
---

# CHK-0001 Short Name

## Preconditions
## Checks
- [ ] Build passes
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Documentation updated
- [ ] Related markdown artifacts updated

## Evidence
## Exceptions
```

### 4.5 TODO Files

TODO files hold future work that should not block the current change.

Path: `work/todos/TODO-####-short-name.md`

Required sections:

```markdown
---
id: TODO-0001
type: todo
status: open | scheduled | closed | abandoned
owner: backlog
source_task: TASK-0001
related_journeys: []
related_files: []
updated: 2026-05-02
---

# TODO-0001 Short Name

## Context
## Why Deferred
## Proposed Future Work
## Impact If Ignored
## Revisit Trigger
```

### 4.6 Decision Files

Decision files record durable architectural or product choices.

Path: `work/decisions/ADR-####-short-name.md`

Required sections:

```markdown
---
id: ADR-0001
type: decision
status: proposed | accepted | superseded
owner: planner
related_designs: []
related_files: []
updated: 2026-05-02
---

# ADR-0001 Short Name

## Context
## Decision
## Consequences
## Alternatives Considered
## Supersedes
```

### 4.7 Change Files

Change files are generated or agent-maintained manifests that bind implementation edits to workflow artifacts.

Path: `work/changes/CHG-####-short-name.md`

Required sections:

```markdown
---
id: CHG-0001
type: change
status: open | verified | merged | reverted
owner: worker-a
related_task: TASK-0001
related_review: REV-0001
updated: 2026-05-02
---

# CHG-0001 Short Name

## Summary
## Files Changed
| File | Reason | Related Artifact |
|---|---|---|

## Consistency Updates
| Artifact | Required Update | Status |
|---|---|---|

## Commands Run
## Verification Evidence
## Known Gaps
```

### 4.8 Review Files

Review files capture code review findings and disposition.

Path: `work/reviews/REV-####-short-name.md`

Required sections:

```markdown
---
id: REV-0001
type: review
status: requested | changes_requested | approved | closed
owner: reviewer
related_task: TASK-0001
related_change: CHG-0001
updated: 2026-05-02
---

# REV-0001 Short Name

## Scope Reviewed
## Findings
## Required Fixes
## Verification Reviewed
## Approval Criteria
## Final Decision
```

---

## 5. User Journeys for Software Automation

The markdown workflow must support the full software lifecycle.

### 5.1 New Feature Journey

1. User requests a feature.
2. Planner creates or updates one or more `JRN-*` files.
3. Planner creates `DES-*` if implementation is non-trivial.
4. Planner creates `TASK-*` files split by ownership.
5. Worker agents claim tasks, update status to `in_progress`, and edit code.
6. Workers maintain `CHG-*` files as files change.
7. Test agent updates `CHK-*` with evidence.
8. Reviewer creates `REV-*`, records findings, and links required fixes.
9. Worker resolves findings and updates task result.
10. Supervisor marks journey/design/task/change/review artifacts complete.

### 5.2 Bug Fix Journey

1. User or monitoring reports a defect.
2. Triage agent creates a journey or links to an existing one.
3. Worker creates a task with reproduction steps and expected behavior.
4. Worker changes code and adds regression tests.
5. Change file lists affected code, tests, docs, and configs.
6. Checklist proves the bug is fixed and no related flow regressed.
7. Review file records the defect cause and fix acceptance.

### 5.3 Refactor Journey

1. Planner creates a design with explicit non-functional goals.
2. Task files define boundaries so agents avoid conflicting edits.
3. Change files map moved or renamed symbols to impacted docs/tests.
4. Consistency checker verifies imports, references, generated files, and docs.
5. Review focuses on behavior preservation and test adequacy.

### 5.4 Test/Quality Journey

1. Test agent reads active journeys and designs.
2. Test agent creates checklists covering acceptance criteria.
3. Worker or test agent adds missing tests.
4. Verification evidence is written into task, checklist, and change files.
5. Gaps become TODO files with revisit triggers.

### 5.5 Documentation Journey

1. Documentation agent reads changed files and related artifacts.
2. It updates user docs, architecture docs, API docs, examples, and changelogs.
3. Change file records every documentation update or explains why none was needed.
4. Review confirms docs match current behavior.

### 5.6 Dependency or Config Change Journey

1. Planner creates a task with explicit blast radius.
2. Worker updates config, lockfiles, CI, deployment docs, and compatibility notes.
3. Consistency checker validates references across docs and scripts.
4. Checklist includes build, test, lint, and deploy dry-run where available.

### 5.7 Failed Automation Recovery Journey

1. Supervisor detects stale heartbeat, blocked task, failed test, or incomplete change.
2. Supervisor reads the latest task/change/review/checklist artifacts.
3. It reassigns the task or creates a recovery task.
4. New worker continues from markdown state without relying on hidden chat context.
5. Recovery result records what was resumed, repeated, skipped, or invalidated.

### 5.8 Release Journey

1. Release planner creates a release journey.
2. Agents aggregate completed tasks and changes into a release checklist.
3. Reviewers verify unresolved TODOs, known gaps, and migration notes.
4. Release artifact links code changes, tests, docs, and rollback plan.
5. Supervisor archives completed rooms and closes related markdown artifacts.

---

## 6. Consistency Model

Every file modification must be checked against related artifacts and affected files.

### 6.1 Required Cross-Links

Each task must link to at least one journey, design, bug report, or explicit user request. Each change must link to exactly one primary task. Every changed source, test, config, or doc file must appear in the related change file.

### 6.2 Consistency Index

Generate `work/generated/consistency-index.json` from frontmatter and changed files.

Suggested schema:

```json
{
  "artifacts": {
    "TASK-0001": {
      "path": "work/tasks/TASK-0001-implement-login.md",
      "type": "task",
      "status": "in_progress",
      "related_files": ["src/auth.py", "tests/test_auth.py"],
      "related_artifacts": ["JRN-0001", "DES-0001", "CHG-0001"]
    }
  },
  "files": {
    "src/auth.py": {
      "related_artifacts": ["TASK-0001", "CHG-0001", "DES-0001"],
      "last_verified_by": "CHK-0001"
    }
  },
  "stale": []
}
```

### 6.3 Consistency Rules

Agents must enforce these rules before marking work done:

| Rule | Requirement |
|---|---|
| Artifact completeness | Required frontmatter and sections exist for every artifact type. |
| Link integrity | Referenced artifact IDs and files exist. |
| Changed-file coverage | Every changed file appears in a `CHG-*` file with a reason. |
| Design alignment | Source changes that affect architecture, APIs, data models, or behavior update related `DES-*` and `ADR-*` files. |
| Journey alignment | User-visible behavior changes update related `JRN-*` acceptance criteria. |
| Test alignment | Behavior changes include tests or an explicit gap in `CHK-*` and `TODO-*`. |
| TODO discipline | Deferred work has owner, impact, and revisit trigger. |
| Status coherence | A task cannot be `done` while linked review is `changes_requested`, checklist has failed checks, or change is unverified. |
| Staleness detection | Artifacts with related files modified after artifact `updated` date are flagged. |

---

## 7. Agent Responsibilities

### Planner Agent

Creates journeys, designs, task breakdowns, and decision records. It owns scope clarity and dependency mapping.

### Worker Agent

Claims task files, edits implementation files, maintains change files, and records verification commands.

### Test Agent

Creates and executes checklist files. It updates task and change artifacts with evidence and gaps.

### Review Agent

Creates review files, records findings first, verifies consistency links, and approves or requests changes.

### Documentation Agent

Updates user-facing and architecture docs when behavior, APIs, setup, or operations change.

### Supervisor Agent

Maintains `work/index.md`, detects stale or inconsistent artifacts, reassigns blocked tasks, and closes completed work.

---

## 8. Agentroom Integration

Markdown artifacts should be referenced in Agentroom messages instead of copied into every message.

Recommended A2A payload fields:

```json
{
  "schema": "agentroom.a2a.v1",
  "type": "task.update",
  "intent": "claim_task",
  "summary": "worker-a is starting TASK-0001",
  "artifacts": ["work/tasks/TASK-0001-implement-login.md"],
  "related_files": ["src/auth.py", "tests/test_auth.py"],
  "status": "in_progress"
}
```

Recommended room topics:

| Room | Purpose |
|---|---|
| `project:<repo>` | Main coordination room. |
| `goal:<journey-id>` | Journey-specific planning and status. |
| `task:<task-id>` | Focused execution thread. |
| `review:<review-id>` | Review discussion and findings. |
| `release:<release-id>` | Release readiness and closure. |

---

## 9. Automation Commands

Add an `agentctl work` command group or a separate `agentwork` CLI.

```bash
agentctl work init
agentctl work new journey "User login"
agentctl work new design --journey JRN-0001 "Auth flow"
agentctl work new task --design DES-0001 "Implement login"
agentctl work claim TASK-0001 --agent worker-a
agentctl work change TASK-0001 --files src/auth.py tests/test_auth.py
agentctl work check
agentctl work graph
agentctl work close TASK-0001
```

Minimum command behavior:

| Command | Behavior |
|---|---|
| `work init` | Creates directory tree, README, index, and templates. |
| `work new` | Creates typed artifacts with valid IDs and frontmatter. |
| `work claim` | Sets owner/status and emits Agentroom `task.claimed`. |
| `work change` | Creates or updates `CHG-*` with changed-file mapping. |
| `work check` | Runs schema, link, changed-file, status, and staleness checks. |
| `work graph` | Generates artifact graph and consistency index. |
| `work close` | Verifies closure rules before setting status to done/verified/closed. |

---

## 10. Implementation Roadmap

### Phase 1: Templates and Conventions

1. Create `work/` directory structure.
2. Add markdown templates for every artifact type.
3. Define frontmatter schema and status transitions.
4. Document agent responsibilities in `work/README.md`.

Exit criteria: agents can create valid artifacts manually or from templates.

### Phase 2: Validation

1. Implement markdown parser using frontmatter plus heading validation.
2. Validate artifact IDs, links, related files, and required sections.
3. Generate `work/generated/consistency-index.json`.
4. Generate `work/generated/stale-artifacts.md`.

Exit criteria: `agentctl work check` can fail inconsistent work before completion.

### Phase 3: Change Tracking

1. Detect changed files from Git when available.
2. Require each changed file to be listed in a `CHG-*` artifact.
3. Flag source files without tests, docs, or explicit exemptions when behavior changes.
4. Add status coherence checks across task, change, checklist, and review files.

Exit criteria: an agent cannot close a task with undocumented or unverified modifications.

### Phase 4: Agentroom Events

1. Emit A2A events when artifacts are created, claimed, updated, blocked, reviewed, or closed.
2. Include artifact paths and related files in event payloads.
3. Allow agents to discover work by querying active task artifacts.
4. Archive task rooms when corresponding artifacts close.

Exit criteria: room messages and markdown state stay synchronized.

### Phase 5: Recovery and Handoff

1. Add stale-task detection based on owner heartbeat and artifact timestamps.
2. Generate recovery summaries for blocked or abandoned tasks.
3. Support reassignment without relying on hidden model context.
4. Add supervisor reports for active, blocked, stale, and ready-for-review work.

Exit criteria: a new agent can resume work from files alone.

### Phase 6: Release Readiness

1. Aggregate completed tasks, changes, reviews, and TODOs into release checklists.
2. Verify every user journey has acceptance evidence or explicit deferral.
3. Produce release notes and rollback notes from artifacts.
4. Close or archive completed artifacts after release.

Exit criteria: releases can be audited from markdown plus Agentroom logs.

---

## 11. Completion Gates

An automated coding agent may mark a task `done` only when all of these are true:

1. The task has a linked journey, design, bug, or user-request artifact.
2. Every changed file is listed in a change file with a reason.
3. Related design, journey, decision, documentation, and TODO files are updated or explicitly marked not applicable.
4. Verification commands and results are recorded.
5. Review status is `approved` or no review is required by policy.
6. No linked checklist item is failed or unchecked unless it has a documented exception.
7. `agentctl work check` passes.

---

## 12. Initial Templates to Build

Create these first:

```text
work/templates/journey.md
work/templates/design.md
work/templates/task.md
work/templates/checklist.md
work/templates/todo.md
work/templates/decision.md
work/templates/change.md
work/templates/review.md
```

Each template should include frontmatter, required sections, and short inline comments that tell agents what evidence belongs in each section.

---

## 13. Open Design Decisions

1. Should active work artifacts live in `work/`, `.agents/work/`, or `doc/work/`?
2. Should artifact IDs be global counters, timestamp-based, or room-scoped?
3. Should `agentctl work check` require Git, or support non-Git workspaces with filesystem snapshots?
4. Which status transitions require reviewer approval?
5. How strict should documentation-update requirements be for internal-only code changes?
6. Should generated consistency files be committed or treated as local state?

