# Agent Review Rules

Project-wide review standards binding on all agents conducting code reviews in this repository.

## 1. Review Philosophy

- **Reviews are gates, not suggestions.** Every finding must be classified as `blocking` or `non-blocking`. Blocking findings must be resolved before approval.
- **Be specific.** Cite file paths, line numbers, and the exact rule violated.
- **Separate style from substance.** Style issues are non-blocking unless they violate `coding-rules.md` §2 or §8.
- **Assume good intent.** Frame findings as actionable improvements, not personal criticism.

## 2. Required Review Checklist

Every review must verify the following. Record the result in the `REV-*` artifact.

### 2.1 Scope & Completeness
- [ ] The change addresses **only** the linked task. No scope creep.
- [ ] All files listed in the `CHG-*` artifact were reviewed.
- [ ] No files were edited that are not listed in the change manifest.
- [ ] Related markdown artifacts (task, design, checklist) are consistent with the code.

### 2.2 Correctness
- [ ] The logic is correct for the stated requirement.
- [ ] Edge cases are handled or explicitly documented as out-of-scope.
- [ ] No regressions: existing tests still pass.
- [ ] New tests cover the new behavior (unit or integration, not just happy-path).

### 2.3 Coding Rules Compliance
- [ ] Code follows `coding-rules.md` §2 (Python style & types).
- [ ] No prohibited patterns from `coding-rules.md` §8 are present.
- [ ] Error handling is specific and does not swallow exceptions.
- [ ] Functions are focused and reasonably sized.

### 2.4 Security
- [ ] No user input is used to construct paths, commands, or queries unsafely.
- [ ] No secrets or credentials are hard-coded or logged.
- [ ] Path traversal inputs are rejected at boundaries.
- [ ] No injection vulnerabilities (command, SQL, XSS, etc.).

### 2.5 Testing & Verification
- [ ] New code has test coverage.
- [ ] Tests are deterministic and do not rely on external services.
- [ ] Test output evidence is recorded in the task/checklist artifact.
- [ ] The reviewer ran the test suite or verified CI passed.

### 2.6 Documentation & Consistency
- [ ] Public APIs have docstrings.
- [ ] User-facing behavior changes are reflected in docs or README.
- [ ] `CHANGELOG` or version metadata is updated if the project uses them.
- [ ] `ownership.md` is current if file ownership changed.

## 3. Review Severity Levels

| Level | Definition | Resolution Required |
|---|---|---|
| **blocking** | Bug, security risk, or violation of binding coding rule | Must fix before approval |
| **serious** | Significant maintainability or correctness concern | Should fix; can discuss override |
| **minor** | Style, naming, or nitpick | Non-blocking; author may address or explain |
| **question** | Unclear intent or missing context | Non-blocking; author should clarify |

## 4. Review Process

### 4.1 Initiating Review
1. The worker sets the task artifact status to `waiting_for_review`.
2. The worker creates a `REV-*` artifact linking the task and change manifest.
3. The worker lists the scope, changed files, and verification evidence.

### 4.2 Conducting Review
1. The reviewer reads the task, design, and change manifest before reading code.
2. The reviewer checks out the branch or reads the diff.
3. The reviewer walks through the Required Review Checklist (§2).
4. The reviewer records each finding with severity, file/line, and rationale.

### 4.3 Recording Findings
Each finding must include:
- **File and location** (e.g., `agentroom/server.py:117`)
- **Rule violated** (e.g., `coding-rules.md §5.1 — path traversal validation missing`)
- **Severity** (`blocking`, `serious`, `minor`, `question`)
- **What** — description of the issue
- **Why** — why it matters
- **How** — concrete fix or alternative

### 4.4 Decision
- **changes_requested**: One or more blocking findings exist.
- **approved**: All blocking findings resolved; serious/minor findings addressed or deferred.
- **closed**: Review abandoned or superseded by a new review.

The reviewer must update the `REV-*` artifact with the final decision and rationale.

## 5. Fix Verification

When a worker addresses review findings:
1. The worker updates the task artifact with a response to each finding.
2. The worker re-runs tests and updates evidence.
3. The worker updates the `REV-*` artifact, linking the fix commits or file versions.
4. The reviewer verifies blocking fixes and updates the review decision.

## 6. Fast-Track Reviews

A review may be marked `fast_track` (non-blocking by default) **only** when **all** of the following are true:
- The change is ≤ 20 lines.
- No user-facing APIs are modified.
- No security-sensitive code paths are touched.
- The change is a pure refactor with existing test coverage.
- The worker records explicit justification in the task artifact.

Even fast-track changes must have a `REV-*` artifact for auditability.

## 7. Review Disputes

If a worker disagrees with a blocking finding:
1. The worker responds in the `REV-*` artifact with rationale.
2. If unresolved after one round-trip, escalate to the supervisor agent.
3. The supervisor records the override decision in the review artifact and updates `ownership.md`.

## 8. Prohibited Review Behaviors

- Approving without reading the code.
- Raising blocking findings without citing a specific rule or concrete bug.
- Introducing new requirements (features, refactors) not in the original task.
- Skipping the security checklist for changes touching input parsing, auth, or network boundaries.
- Leaving a review in an ambiguous state (always render a decision).

---

*These rules are binding. A review artifact that does not contain the Required Review Checklist (§2) is incomplete and must be returned to the reviewer.*
