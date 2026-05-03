# Fully Automated Agent Working Protocol (FAAWP)

## 1. Core Philosophy: Documentation-Driven Automation (DDA)
To achieve full automation while maintaining perfect context and consistency, AI agents must operate under a **Documentation-Driven** paradigm. The agent's memory and working context are externalized into a strictly managed set of Markdown documents.

**The Golden Rule:** The documentation is the single source of truth. Code is merely a byproduct of the documentation.

## 2. The Strict Workflow Rules

### Rule 1: Docs First, Always
An agent is strictly prohibited from executing code changes, running commands, or modifying state without first producing or updating the corresponding **Design Document** and **Task Document**.

### Rule 2: Document Consistency Precedes Code Consistency
When a change in requirements or logic occurs:
1. The agent must pause all implementation.
2. The agent must traverse the documentation hierarchy (Design -> Task -> Checklist -> Testing) and update it to reflect the new state.
3. Only after all documents are consistent may the agent resume code modification.

### Rule 3: Explicit State Tracking
Agents do not rely on implicit memory or LLM context windows to remember what they have done. Instead, they strictly maintain a `checklist.md` or embedded checklist within the `task_doc.md`. Every completed step must be checked off (`[x]`) before moving to the next.

## 3. The Markdown Documentation Typology
To clarify their work, agents must utilize the following suite of Markdown documents. Every project or major feature must have this structure:

*   **`design.md` (Design Document):** High-level architecture, "Why" and "What".
*   **`task.md` (Task Document):** The "How". Step-by-step implementation plan.
*   **`checklist.md` (Execution Checklist):** Granular, line-by-line tracker of current progress.
*   **`testing.md` (Testing & Validation Document):** Pre-defined success criteria and testing protocols.
*   **`context_ledger.md` (Optional):** A running log of major decisions, roadblocks, and context shifts.

## 4. The Agent Execution Loop

1. **Ingest Phase:** Agent reads the user request and immediately creates/updates `design.md`.
2. **Planning Phase:** Agent derives `task.md` and `checklist.md` from the design doc.
3. **Approval/Review Phase (Optional but Recommended):** Agent presents the docs to the user or a reviewer agent.
4. **Execution Phase:** Agent reads the first unchecked item in `checklist.md`.
    * If the step requires modifying existing logic, the agent verifies `design.md` is still accurate. If not, goto Phase 1.
    * Agent executes the step (writes code, runs tests).
5. **Verification Phase:** Agent runs tests according to `testing.md`.
6. **Commit Phase:** Agent marks the step as `[x]` in `checklist.md` and moves to the next step.

## 5. Directory Structure Convention
All automated agent work should reside in a structured environment:
```text
project_root/
├── docs/
│   ├── design.md
│   ├── task.md
│   ├── checklist.md
│   └── testing.md
├── src/
└── tests/
```
