---
id: CHK-0001
type: checklist
status: retired
owner: codex
related_tasks: ["TASK-0001"]
related_files:
  - agentroom/
  - tests/
  - pyproject.toml
updated: 2026-05-03
---

# CHK-0001 Agentroom MVP Validation

## Preconditions
- Python 3.11+ available.
- Work is run from repository root.

## Checks
- [x] Package imports.
- [x] Unit tests pass.
- [x] CLI help renders.
- [x] HTTP server module imports.
- [x] Related markdown artifacts updated.

## Evidence
- `python - <<'PY' ... import agentroom; import agentroom.server ... PY` printed `0.1.0`.
- `python -m unittest discover -s tests -v` ran 7 tests and passed.
- `python -m agentroom.cli --help` rendered the top-level CLI help.
- `python -m compileall agentroom tests` completed successfully.
- CLI smoke flow created `project:smoke`, posted `hello`, and listed both messages.

## Exceptions
- No external service integration tests for webhook delivery or LLM adapters in MVP.
