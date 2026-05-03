---
id: ADR-0001
type: decision
status: accepted
owner: planner
related_designs: []
related_files:
  - agent_protocol/coding-rules.md
updated: 2026-05-03
---

# ADR-0001 Project-Wide Agent Coding Rules

## Context

As multiple agents edit the same Python codebase, inconsistency in style, quality, security practices, and testing discipline creates friction. Reviews become bikeshedding sessions, security vulnerabilities slip through, and tests become flaky. Without a single source of truth for coding standards, agents cannot reliably predict what is acceptable.

## Decision

Adopt `agent_protocol/coding-rules.md` as the binding, project-wide coding standard for all agents. The rules cover:

1. Golden rules (read before writing, no speculative abstractions, trust internal boundaries).
2. Python style (PEP 8, 120-char line length, type annotations, import ordering).
3. Code quality (function size, error handling, side effects, mutability).
4. Testing (coverage requirements, pytest style, mocking, test data hygiene).
5. Security (input validation, injection prevention, secrets handling).
6. Documentation (docstrings, comments).
7. Agent-specific practices (pre-edit, during-edit, post-edit checklists).
8. Prohibited patterns with explicit replacements.

## Consequences

- **Easier:** Reviews are faster because standards are explicit. Agents know what is expected before writing code.
- **Easier:** Security review is repeatable; the security checklist in `coding-rules.md` §5 is deterministic.
- **Harder:** Agents must read the rules before editing. This adds a small upfront cost to every task.
- **Harder:** Violations must be fixed before review approval. This may increase iteration count initially.

## Alternatives Considered

- **Rely on linters only (ruff, mypy):** Rejected. Linters enforce syntax but not architectural discipline (e.g., "no speculative abstractions", "trust internal boundaries").
- **Embed rules in AGENTS.md:** Rejected. AGENTS.md is for coordination protocol; mixing coding standards would make both documents too long and hard to update independently.
- **Per-module rules:** Rejected. A single project-wide rule keeps cognitive load low and makes cross-module contributions predictable.

## Supersedes

None.
