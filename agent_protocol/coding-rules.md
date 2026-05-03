# Agent Coding Rules

Project-wide coding standards binding on all agents editing code in this repository.

## 1. Golden Rules

1. **Read before writing.** Never edit a file you have not read in full.
2. **No speculative abstractions.** Solve the problem at hand; do not design for hypothetical future requirements.
3. **Trust internal boundaries.** Do not add validation, fallbacks, or error handling for scenarios that cannot happen inside the codebase. Validate only at system boundaries (user input, external APIs, CLI arguments).
4. **Prefer editing existing files.** Do not create new files unless the task explicitly requires them.
5. **Do no harm.** Never introduce security vulnerabilities (OWASP Top 10). If you spot one you did not create, flag it immediately.

## 2. Python Style

### 2.1 Formatting
- Follow PEP 8 with a line-length budget of **120 characters**.
- Use double quotes for strings unless single quotes avoid escaping.
- Use trailing commas in multi-line collections.
- Import order: `__future__`, stdlib, third-party, first-party. Separate groups with a blank line.

### 2.2 Types
- Use type annotations on all public functions and methods.
- Use `from __future__ import annotations` in every module.
- Prefer `dict[str, Any]` over `Dict[str, Any]`; use built-in generic aliases.
- Avoid `Any` when a narrower type is knowable.

### 2.3 Naming
- `snake_case` for functions, variables, methods.
- `PascalCase` for classes.
- `UPPER_CASE` for module-level constants.
- Prefix private helpers with `_`. Prefix truly internal module names with `_`.

## 3. Code Quality

### 3.1 Functions
- Keep functions under **40 lines** where practical.
- A function should do **one thing**.
- Limit arguments to **4 or fewer**; use dataclasses or typed dicts for larger bundles.

### 3.2 Error Handling
- Raise specific exceptions (`ValueError`, `KeyError`, custom subclasses). Avoid bare `raise` or `except Exception` unless re-raising immediately.
- Log errors at the appropriate level (`ERROR` for unexpected failures, `WARNING` for recoverable issues, `INFO` for milestones).
- Never swallow exceptions silently.

### 3.3 Side Effects & Mutability
- Prefer pure functions. Isolate I/O and mutation at the edges of modules.
- Do not mutate function arguments unless the API contract explicitly allows it.
- Use dataclasses with `frozen=True` for value objects where possible.

## 4. Testing

### 4.1 Required Coverage
- Every bug fix must include a regression test.
- Every new feature must include at least one integration-level test.
- Tests must be runnable with `pytest` and must not require external services to pass.

### 4.2 Test Style
- Use `pytest` fixtures and parametrization.
- Use descriptive test names: `test_<scenario>_<expected_result>`.
- One assertion concept per test; use helper functions for complex setups.
- Mock external APIs and subprocess calls. Mock at the lowest practical boundary.

### 4.3 Test Data
- Use factories or fixtures for test data, not hard-coded magic values scattered across tests.
- Clean up temp files and state directories in `tearDown` / `addfinalizer`.

## 5. Security

### 5.1 Input Validation
- Validate and sanitize all user-facing input at the system boundary.
- Reject path traversal sequences (`../`, `..\`) in any path constructed from user input.
- Reject empty or whitespace-only identifiers.

### 5.2 Injection Prevention
- Never construct shell commands by string concatenation with user input.
- Never construct SQL, HTML, or URLs by concatenation without escaping.
- Use parameterized interfaces (prepared statements, `urllib.parse`, `html.escape`).

### 5.3 Secrets
- Never commit secrets, API keys, tokens, or passwords.
- Never log secrets or PII at `INFO` or lower levels.
- Use environment variables or secret managers for configuration.

## 6. Documentation

### 6.1 Docstrings
- Every public module, class, and function must have a docstring.
- Use Google-style or NumPy-style docstrings consistently.
- Document raised exceptions and return types.

### 6.2 Comments
- Comments explain **why**, not **what**.
- If the code is unclear, rewrite the code rather than adding a comment.
- Keep comments within 80 characters.

## 7. Agent-Specific Practices

### 7.1 Before Editing
1. Read the full target file.
2. Check `agent_protocol/work/ownership.md` for active claims.
3. Read related artifacts (task, design, checklist) linked in the claim.
4. Record your intended changes in the task artifact **before** editing code.

### 7.2 While Editing
1. Make the smallest change that satisfies the requirement.
2. Do not refactor unrelated code.
3. Do not add docstrings, type annotations, or comments to code you did not change.
4. Do not add feature flags or backwards-compatibility shims unless explicitly required.

### 7.3 After Editing
1. Run the relevant tests and paste the output into the task artifact.
2. Update `agent_protocol/work/ownership.md` if file ownership changed.
3. Create or update the `CHG-*` artifact listing every changed file and the rationale.
4. Mark the task artifact with current status and evidence.

## 8. Prohibited Patterns

| Pattern | Replacement |
|---|---|
| `except:` or `except Exception:` | Catch specific exceptions only |
| `eval()`, `exec()`, `compile()` on user input | Use `ast.literal_eval` or a safe parser |
| `os.system()` or `subprocess.call()` with unsanitized strings | Use `subprocess.run()` with `shlex.quote()` or list args |
| Mutable default arguments (`def fn(x=[]`) | Use `None` default and initialize inside |
| Global mutable state | Encapsulate in classes or closures |
| `time.sleep()` in production polling loops | Use event-driven or backoff strategies |
| Copy-paste duplication | Extract a shared helper |

---

*These rules are binding. Violations discovered in review must be fixed before approval.*
