# Agent Markdown Working Protocol Design

## 1. Purpose

This document extends the markdown workflow plan with a concrete working
protocol for aligned coding agents.

The workflow plan defines artifact types. This protocol defines how agents use
those artifacts to coordinate with each other before, during, and after work.

The central rule is:

> Agents do not coordinate through private memory. Agents coordinate by keeping
> shared markdown artifacts current, specific, and resumable.

Agentroom remains the event stream for announcements and routing. Markdown files
are the durable coordination surface. An agent should be able to join a task,
read the linked markdown files, and understand the goal, ownership boundary,
current state, evidence, and next action without relying on hidden chat context.

---

## 2. Protocol Principles

### 2.1 Artifacts Are Contracts

Task, design, change, checklist, and review files are operational contracts, not
loose notes.

An agent must not treat a task as ready unless its goal, scope, ownership, and
verification expectations are clear. Once a worker claims a task, other agents
should treat the task file as the current contract for that work unless it is
blocked, stale, or contradicted by source code.

### 2.2 Write Intent Before Acting

Before editing code, a worker records intended changes in the task file or
change file.

This gives other agents an early signal about direction and reduces conflicting
parallel edits.

### 2.3 Separate Intent, State, and Evidence

Agents must distinguish:

| Category | Meaning |
|---|---|
| Intent | What the agent plans to do. |
| State | What is currently true. |
| Evidence | How the agent verified it. |

Completion cannot be inferred from intent or optimistic status text. Completion
requires recorded evidence.

### 2.4 Preserve Coordination History

Coordination-sensitive sections should be append-only where practical:

- Scope changes.
- Blockers.
- Failed verification.
- Review findings.
- Handoff notes.
- Recovery notes.
- Important assumptions discovered during work.

Agents may update summaries and status fields, but they should not erase facts
that explain why previous agents acted.

### 2.5 Make Non-Changes Explicit

When an agent decides that no design, journey, test, or documentation update is
needed, it must record that decision with a short reason. Silent omission makes
future agents repeat the same analysis.

---

## 3. Agent Lifecycle

Agents should move through explicit working states.

| State | Required Behavior |
|---|---|
| `idle` | Look for ready tasks or supervisor instructions. |
| `discovering` | Read linked artifacts and inspect relevant files. |
| `claiming` | Claim a task with owner, heartbeat, and expected files. |
| `working` | Record intended changes, edit files, and update change records. |
| `blocked` | Record blocker, attempted resolution, and needed decision. |
| `waiting_for_review` | Stop feature work and expose evidence for review. |
| `fixing_review` | Address review findings and update review disposition. |
| `handoff` | Record current state, touched files, commands run, and next action. |
| `done` | Close only after verification and consistency checks pass. |
| `stale` | Eligible for supervisor recovery or reassignment. |

Recommended task frontmatter:

```yaml
owner: worker-a
agent_state: working
heartbeat: 2026-05-03T14:12:00Z
claim_expires: 2026-05-03T14:42:00Z
coordination_status: clear
```

---

## 4. Alignment Gates

Agents should pass lightweight gates at major transitions.

### 4.1 Before Claim

The task is claimable only when:

- Objective is clear.
- Scope and out-of-scope are present.
- Ownership boundary is stated.
- Dependencies are satisfied or documented.
- Expected verification path exists.
- Priority is set.

If these are missing, the agent should update the task, request planning, or
create a blocker instead of beginning implementation.

### 4.2 Before Editing

Before modifying files, the worker must:

- Read linked journey, design, task, and change artifacts.
- Check active tasks for overlapping file ownership.
- Record intended changes.
- Record files expected to change.
- Mark coordination risk if overlap exists.

### 4.3 Before Review

Before requesting review, the worker must:

- List all changed files in a change file.
- Record verification commands and results.
- Record known gaps or explicit exceptions.
- Update consistency decisions.
- Mark the task as ready for review.

### 4.4 Before Close

Before closing a task, the supervisor or closing agent must verify:

- Change file coverage is complete.
- Verification evidence exists.
- Review is approved or explicitly not required.
- Linked checklist has no unchecked blocking item.
- Deferred work has TODO records.
- Agentroom and markdown status agree.

---

## 5. Ownership and Conflict Protocol

Each task should declare file ownership.

```yaml
owned_files:
  - src/auth/session.py
read_only_files:
  - src/auth/config.py
coordination_required_files:
  - src/auth/__init__.py
```

Usage:

| Field | Meaning |
|---|---|
| `owned_files` | The worker may edit these files for the task. |
| `read_only_files` | The worker may inspect these files but should not edit them. |
| `coordination_required_files` | The worker must announce intent before editing. |

Conflict rules:

1. A worker must not edit a file owned by another active task without
   coordination.
2. If a needed file is not listed, the worker updates the task before editing.
3. If two active tasks require the same file, set `coordination_status:
   overlap_risk`.
4. If overlap cannot be resolved locally, set `coordination_status:
   needs_supervisor`.

Recommended coordination statuses:

```text
clear
overlap_risk
blocked_by_other_task
needs_supervisor
```

---

## 6. Handoff and Recovery Protocol

A task must be resumable from markdown alone.

Every task should include:

```markdown
## Handoff
- Last completed step:
- Current working state:
- Files touched:
- Commands already run:
- Known failures:
- Next recommended action:
```

Rules:

1. Any agent stopping before completion must update handoff.
2. A recovering agent must read handoff before acting.
3. Supervisor may reassign a task when `claim_expires` has passed and heartbeat
   is stale.
4. Recovery work should record what was reused, repeated, skipped, or
   invalidated.

---

## 7. Concrete Docs Agents Need

Agents need a small set of durable documents with clear usage rules. The table
below lists the recommended docs, who uses them, and when.

| Document | Path | Primary Users | Usage |
|---|---|---|---|
| Work README | `work/README.md` | All agents | Explains repository-specific workflow rules, artifact conventions, status meanings, and escalation policy. Read before creating or claiming work. |
| Work Index | `work/index.md` | Supervisor, planner, all agents | Current map of active journeys, tasks, blocked work, review queue, and release state. Used for discovery and prioritization. |
| Agent Protocol | `work/protocol.md` | All agents | Defines required lifecycle states, alignment gates, ownership rules, handoff rules, and completion gates. Used as the behavioral contract for agents. |
| Journey | `work/journeys/JRN-####-name.md` | Planner, worker, tester, reviewer | Defines user goal, flows, and acceptance criteria. Used to keep implementation and tests aligned with user-visible behavior. |
| Design | `work/designs/DES-####-name.md` | Planner, worker, reviewer, docs agent | Defines implementation approach, constraints, interfaces, data model, risks, and rollout. Used to align code changes with architecture. |
| Decision | `work/decisions/ADR-####-name.md` | Planner, reviewer, future agents | Records durable architectural or product choices. Used to avoid reopening settled decisions without context. |
| Task | `work/tasks/TASK-####-name.md` | Worker, supervisor, reviewer | Executable work contract. Used to claim work, define scope, record intent, track state, manage ownership, and hand off. |
| Change | `work/changes/CHG-####-name.md` | Worker, reviewer, supervisor | Maps changed files to reasons and related artifacts. Used for consistency checks and review scope. |
| Checklist | `work/checklists/CHK-####-name.md` | Tester, worker, reviewer | Defines verification procedure and evidence. Used to prove behavior and capture exceptions. |
| Review | `work/reviews/REV-####-name.md` | Reviewer, worker, supervisor | Records findings, required fixes, reviewed evidence, and approval decision. Used to close review loops. |
| TODO | `work/todos/TODO-####-name.md` | Planner, supervisor, future workers | Captures deferred work with impact and revisit trigger. Used to prevent lost follow-ups. |
| Agent Roster | `work/agents.md` | Supervisor, all agents | Lists active agents, roles, current task, heartbeat, and claim expiry. Used to detect stale work and avoid duplicate claims. |
| Ownership Map | `work/ownership.md` | Worker, supervisor | Lists active file ownership and coordination-required areas. Used before editing files. |
| Verification Policy | `work/verification.md` | Worker, tester, reviewer | Defines required commands, evidence format, exception policy, and minimum test expectations by task type. |
| Review Policy | `work/review-policy.md` | Reviewer, supervisor, worker | Defines which changes require review, who may approve, and what approval means. |
| Release Checklist | `work/releases/REL-####-name.md` | Release planner, supervisor, reviewer | Aggregates completed tasks, changes, TODOs, verification, known gaps, rollback notes, and release decision. |
| Consistency Index | `work/generated/consistency-index.json` | Tools, supervisor, all agents | Generated graph of artifacts and files. Used by checks and agents to find related context. |
| Active Tasks Report | `work/generated/active-tasks.md` | Supervisor, idle agents | Generated queue of claimable, in-progress, blocked, and review-ready tasks. Used for work selection. |
| Stale Claims Report | `work/generated/stale-claims.md` | Supervisor | Generated report of expired claims and missing heartbeats. Used for recovery. |
| Review Queue | `work/generated/review-queue.md` | Review agents, supervisor | Generated list of tasks waiting for review and their evidence. Used for review assignment. |
| Unowned Changes Report | `work/generated/unowned-changes.md` | Supervisor, workers | Generated report of modified files not covered by change artifacts. Used to prevent invisible work. |

---

## 8. Recommended Document Schemas

### 8.1 Agent Protocol

Path: `work/protocol.md`

```markdown
# Agent Working Protocol

## Core Rules
## Agent Lifecycle States
## Alignment Gates
## Ownership Rules
## Conflict Resolution
## Handoff Rules
## Completion Gates
## Escalation Rules
```

Usage:

- Read by every agent before acting.
- Updated only by supervisor or planner.
- Referenced by task files when exceptions are needed.

### 8.2 Agent Roster

Path: `work/agents.md`

```markdown
# Agent Roster

| Agent | Role | State | Current Task | Heartbeat | Claim Expires |
|---|---|---|---|---|---|
```

Usage:

- Supervisor updates or generates it.
- Workers consult it before claiming work.
- Stale entries trigger recovery.

### 8.3 Ownership Map

Path: `work/ownership.md`

```markdown
# Ownership Map

## Active File Ownership
| File | Task | Owner | Mode | Since |
|---|---|---|---|---|

## Coordination Required Areas
| Area | Reason | Required Coordination |
|---|---|---|
```

Usage:

- Workers check it before editing.
- Supervisor resolves conflicts.
- Generated from active task frontmatter when possible.

### 8.4 Verification Policy

Path: `work/verification.md`

```markdown
# Verification Policy

## Required Evidence Format
## Minimum Checks By Task Type
## Test Exception Policy
## Failed Verification Handling
## Environment Assumptions
```

Usage:

- Workers use it to know what evidence to record.
- Test agents use it to create checklist files.
- Reviewers use it to judge whether verification is sufficient.

### 8.5 Review Policy

Path: `work/review-policy.md`

```markdown
# Review Policy

## Review Required
## Review Optional
## Approval Authority
## Self-Review Rules
## Finding Severity
## Closure Rules
```

Usage:

- Supervisor determines whether review is required.
- Review agents apply consistent approval criteria.
- Workers know when they may close without review.

---

## 9. Task File Additions for Alignment

Add these sections to task files:

```markdown
## Shared Understanding
- Goal:
- Non-goals:
- Expected behavior:
- Risk areas:
- Files likely affected:
- Verification expected:

## Intended Changes

## Observed Reality

## Current Status

## Consistency Decisions
- Journey update:
- Design update:
- Decision update:
- Tests:
- Docs:
- TODOs:

## Handoff
- Last completed step:
- Current working state:
- Files touched:
- Commands already run:
- Known failures:
- Next recommended action:
```

These sections improve alignment by making intent, discoveries, state, and
handoff explicit.

---

## 10. Agentroom Message Discipline

Agentroom messages should announce transitions and point to artifacts. They
should not become a second source of durable task state.

Recommended message:

```json
{
  "schema": "agentroom.a2a.v1",
  "type": "task.status",
  "agent": "worker-a",
  "task": "TASK-0001",
  "status": "working",
  "summary": "Implementation started; intended changes recorded.",
  "artifacts": [
    "work/tasks/TASK-0001-login.md",
    "work/changes/CHG-0001-login.md"
  ],
  "related_files": [
    "src/auth/session.py"
  ]
}
```

Rules:

1. Every task state transition emits an Agentroom message.
2. Every Agentroom task message links the relevant markdown artifacts.
3. Durable details go in markdown first or immediately after the message.
4. Agentroom summaries should be short enough to route attention.

---

## 11. Supervisor Management Loop

The supervisor should run a repeated management loop:

1. Refresh generated reports.
2. Detect unowned changes.
3. Detect stale claims and expired heartbeats.
4. Detect blocked tasks.
5. Detect review-ready tasks.
6. Assign or expose claimable tasks.
7. Resolve ownership conflicts.
8. Close completed work only after gates pass.

Recommended generated reports:

```text
work/generated/active-tasks.md
work/generated/blocked-tasks.md
work/generated/stale-claims.md
work/generated/review-queue.md
work/generated/unowned-changes.md
work/generated/ready-to-close.md
```

---

## 12. Adoption Order

Implement this protocol in small steps:

1. Add `work/protocol.md`, `work/agents.md`, and `work/ownership.md`.
2. Add task sections for shared understanding, intended changes, observed
   reality, consistency decisions, and handoff.
3. Add owner, heartbeat, claim expiry, and coordination status frontmatter.
4. Generate active task, stale claim, review queue, and unowned change reports.
5. Enforce alignment gates in `agentctl work check`.
6. Emit Agentroom events for claim, heartbeat, block, review, handoff, and close.

This order improves agent alignment early without requiring the full artifact
graph to be implemented first.
