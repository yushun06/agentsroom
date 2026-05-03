# Execution Checklist: [Feature/System Name]

## Reference
*   **Task Doc:** [Link to task.md]

## Instructions for Agent
*   You MUST mark an item as `[x]` ONLY AFTER the task is fully completed, tested, and verified.
*   If you encounter an error, add a sub-bullet describing the error and your mitigation strategy. Do NOT proceed to the next step until resolved.
*   If the plan changes, update `design.md` and `task.md` first, then regenerate this checklist.

## Phase 1: [Phase Name]
- [ ] **Step 1.1:** [Action to take]
  - [ ] Write code for `module_x`
  - [ ] Write unit test for `module_x`
  - [ ] Run test and ensure it passes
- [ ] **Step 1.2:** [Action to take]
  - [ ] ...

## Phase 2: [Phase Name]
- [ ] **Step 2.1:** [Action to take]

---
**Agent State Recovery:** If the agent is restarted or loses context, it must read this file FIRST. The first `[ ]` item indicates exactly where the agent must resume work.
