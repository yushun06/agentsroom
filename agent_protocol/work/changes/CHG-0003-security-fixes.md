---
id: CHG-0003
type: change
status: verified
owner: qoder
related_task: TASK-0002
related_review:
updated: 2026-05-03
---

# CHG-0003 Security and Consistency Fixes

## Summary
Fix DLQ path traversal, webhook URL preservation in DLQ entries, room ID validation before index mutation, and dot-only agent ID rejection.

## Files Changed
| File | Reason |
|---|---|
| `agentroom/delivery/dlq.py` | Sanitize DLQ paths via URL-quoting; reject dot-only agent IDs; store webhook URL in entries |
| `agentroom/delivery/webhook.py` | Pass webhook URL to enqueue_dlq so standalone retry works |
| `agentroom/lifecycle.py` | Validate room_id before mutating index in create_room |
| `tests/test_agentroom.py` | Regression tests for path safety, webhook preservation, empty room ID, dot-only IDs |

## Verification Evidence
- Unit tests: 43 passing.
- `test_dlq_rejects_dot_only_agent_ids` confirms `.` and `..` are rejected.
- `test_dlq_path_safety` confirms `../../etc/passwd` stays inside dlq/.
- `test_dlq_preserves_webhook_url` confirms webhook URL is stored.
- `test_create_room_rejects_empty_id` confirms no orphan index entries.
