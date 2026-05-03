# Ownership Map

## Active File Ownership
| File | Task | Owner | Mode | Since |
|---|---|---|---|---|
| `agentroom/` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |
| `tests/` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |
| `pyproject.toml` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |
| `Dockerfile` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |
| `docker-compose.yml` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |
| `Makefile` | `TASK-0002` | `qoder` | write | 2026-05-03T07:42:00Z |

## Coordination Required Areas
| Area | Reason | Required Coordination |
|---|---|---|
| `agentroom/core.py` | Core storage changes impact all modules. | Announce intent in Agentroom before modifying. |
