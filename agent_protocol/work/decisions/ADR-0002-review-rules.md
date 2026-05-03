---
id: ADR-0002
type: decision
status: accepted
owner: planner
related_designs: []
related_files:
  - agent_protocol/review-rules.md
updated: 2026-05-03
---

# ADR-0002 Project-Wide Agent Review Rules

## Context

Code reviews in agent-driven development have unique requirements: agents need explicit, reproducible criteria; findings must be recorded in durable artifacts; and security checks cannot be skipped because "it's a small change." Without a standardized review process, review quality varies, blocking issues are missed, and review artifacts become incomplete or inconsistent.

## Decision

Adopt `agent_protocol/review-rules.md` as the binding, project-wide review standard for all agents. The rules cover:

1. Review philosophy (gates vs. suggestions, specificity, style vs. substance).
2. Required review checklist (scope, correctness, coding rules compliance, security, testing, documentation).
3. Severity levels (blocking, serious, minor, question) with clear resolution requirements.
4. Review process (initiating, conducting, recording findings, rendering decisions).
5. Fix verification workflow.
6. Fast-track criteria and limits.
7. Dispute escalation path.
8. Prohibited review behaviors.

## Consequences

- **Easier:** Review artifacts are consistent. Every `REV-*` file contains the same structured checklist.
- **Easier:** Security is not optional. The security checklist is mandatory for all reviews.
- **Easier:** Workers know exactly what will be checked, reducing surprise blocking findings.
- **Harder:** Every review must produce a `REV-*` artifact, even fast-track changes.
- **Harder:** Reviewers cannot approve without completing the checklist. This prevents rubber-stamp reviews.

## Alternatives Considered

- **Lightweight reviews for agents:** Rejected. The overhead of a thorough review is lower than the cost of fixing a bug or security issue discovered later.
- **Embed review rules in protocol.md:** Rejected. protocol.md is for lifecycle and coordination; review standards are detailed enough to warrant their own document.
- **Tool-driven reviews only (static analysis):** Rejected. Static analysis catches syntax and some security issues, but cannot evaluate correctness, design consistency, or completeness against task requirements.

## Supersedes

None.
