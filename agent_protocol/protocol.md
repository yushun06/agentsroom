# Agent Working Protocol

## Core Rules
Agents do not coordinate through private memory. Agents coordinate by keeping shared markdown artifacts current, specific, and resumable.
1. Artifacts Are Contracts.
2. Write Intent Before Acting.
3. Separate Intent, State, and Evidence.
4. Preserve Coordination History (append-only where practical).
5. Make Non-Changes Explicit.

## Agent Lifecycle States
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

## Alignment Gates
1. **Before Claim**: Objective clear, scope defined, ownership stated, verification path exists.
2. **Before Editing**: Read artifacts, check overlapping ownership, record intended changes.
3. **Before Review**: List changed files, record verification commands, update consistency.
4. **Before Close**: Change coverage complete, verification evidence exists, review approved.

## Ownership Rules & Conflict Resolution
- A worker must not edit a file owned by another active task without coordination.
- Update `work/ownership.md` and task file before editing unlisted files.
- If overlap risk, set `coordination_status: overlap_risk`.
- If unresolved, set `coordination_status: needs_supervisor`.

## Handoff Rules
A task must be resumable from markdown alone. Any agent stopping before completion must update the `## Handoff` section in the task file. Recovering agents must read handoff before acting.

## Completion Gates
- Verification evidence is complete.
- Review approved or not required.
- All checklist items complete.
- Deferred work captured in TODO artifacts.
- Agentroom messages and markdown status agree.
