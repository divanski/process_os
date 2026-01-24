# Telemetry Database Schema Reference

**Version:** 1.0
**Sprint:** 2
**Last Updated:** 2026-01-20

---

## Overview

ProcessOS telemetry is stored in SQLite databases using a 4-table schema:
- **runs** - Top-level playbook execution records
- **steps** - Individual step executions within runs
- **events** - Immutable telemetry events (critical/high/normal)
- **artifacts** - Generated artifact references

### Entity Relationship

```
runs (1) ──┬── (N) steps
           │
           ├── (N) events
           │
           └── (N) artifacts
                    │
steps (1) ──────────┴── (N) artifacts (created_by_step)
```

---

## Tables

### runs

Top-level execution record for each playbook run.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | TEXT | PRIMARY KEY | Unique run identifier (e.g., "IN-ABC123-run-2026-01-20") |
| `playbook_id` | TEXT | NOT NULL | Playbook identifier |
| `status` | TEXT | NOT NULL, DEFAULT 'running' | running, completed, failed |
| `started_at` | TEXT | NOT NULL | ISO 8601 timestamp |
| `ended_at` | TEXT | NULL | ISO 8601 timestamp (NULL if running) |
| `state_hash` | TEXT | NULL | SHA256 of final state.json |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Indexes:**
- `idx_runs_status_ended_at` on (status, ended_at) - For failed runs queries

---

### steps

Individual step executions within a run.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `step_id` | TEXT | NOT NULL | Step identifier (e.g., "step_1_intake") |
| `run_id` | TEXT | NOT NULL, FK(runs) | Parent run |
| `agent_id` | TEXT | NULL | Agent that executed step |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | pending, started, completed, failed |
| `started_at` | TEXT | NULL | ISO 8601 timestamp |
| `ended_at` | TEXT | NULL | ISO 8601 timestamp |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Primary Key:** (step_id, run_id) - Composite key

**Indexes:**
- `idx_steps_run_id_started_at` on (run_id, started_at) - For timeline queries

---

### events

Immutable telemetry events. **INSERT-only, never UPDATE/DELETE.**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_id` | TEXT | PRIMARY KEY | UUID for event |
| `run_id` | TEXT | NOT NULL, FK(runs) | Parent run |
| `step_id` | TEXT | NULL, FK(steps) | Associated step (NULL for run-level) |
| `agent_id` | TEXT | NULL | Agent identifier |
| `event_type` | TEXT | NOT NULL | Event type (see below) |
| `criticality` | TEXT | NOT NULL | critical, high, normal |
| `timestamp` | TEXT | NOT NULL | ISO 8601 when event occurred |
| `data` | JSON | NULL | Event-specific payload |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Event Types:**
- `run_started` - Run began
- `run_completed` - Run finished successfully
- `run_failed` - Run failed
- `step_started` - Step began
- `step_completed` - Step finished
- `gate_passed` - Gate check passed
- `gate_failed` - Gate check failed
- `artifact_registered` - Artifact created
- `error` - Error occurred

**Indexes:**
- `idx_events_run_id_timestamp` on (run_id, timestamp)
- `idx_events_run_id_step_id_timestamp` on (run_id, step_id, timestamp)
- `idx_events_run_id_event_type_timestamp` on (run_id, event_type, timestamp)
- `idx_events_criticality_run_id` on (criticality, run_id)

---

### artifacts

Artifact references (metadata only, not content).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `artifact_id` | TEXT | PRIMARY KEY | Artifact identifier |
| `run_id` | TEXT | NOT NULL, FK(runs) | Parent run |
| `artifact_kind` | TEXT | NULL | Type (courier_intake_report, detection_report, etc.) |
| `path` | TEXT | NOT NULL | Relative path to file |
| `sha256` | TEXT | NOT NULL | Content hash for integrity |
| `size_bytes` | INTEGER | NULL | File size |
| `content_type` | TEXT | DEFAULT 'text/markdown' | MIME type |
| `created_at` | TEXT | NOT NULL | ISO 8601 when created |
| `created_by_step` | TEXT | NULL, FK(steps) | Step that created artifact |
| `created_at_sys` | TEXT | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Indexes:**
- `idx_artifacts_run_id_kind` on (run_id, artifact_kind)
- `idx_artifacts_sha256` on (sha256)

---

## Query Patterns

### Get Run Summary

```sql
-- Run metadata
SELECT run_id, playbook_id, status, started_at, ended_at
FROM runs WHERE run_id = ?;

-- Counts
SELECT COUNT(*) FROM steps WHERE run_id = ?;
SELECT COUNT(*) FROM events WHERE run_id = ?;
SELECT COUNT(*) FROM artifacts WHERE run_id = ?;
```

### Get Step Timeline

```sql
-- Steps in order
SELECT step_id, agent_id, status, started_at, ended_at
FROM steps
WHERE run_id = ?
ORDER BY started_at ASC;

-- Gate events for each step
SELECT data
FROM events
WHERE run_id = ? AND step_id = ?
  AND event_type IN ('gate_passed', 'gate_failed')
ORDER BY timestamp ASC;

-- Artifacts for each step
SELECT artifact_id
FROM artifacts
WHERE run_id = ? AND created_by_step = ?;
```

### List Failed Runs

```sql
-- Failed runs, most recent first
SELECT run_id, playbook_id, ended_at
FROM runs
WHERE status = 'failed'
ORDER BY ended_at DESC
LIMIT ?;

-- Error reason for each run
SELECT step_id, data
FROM events
WHERE run_id = ? AND event_type = 'error'
ORDER BY timestamp ASC
LIMIT 1;
```

---

## API Methods

The `TelemetryStore` class provides these query methods:

| Method | Returns | Description |
|--------|---------|-------------|
| `get_run_summary(run_id)` | Dict or None | Run metadata + counts |
| `get_step_timeline(run_id)` | Dict or None | Ordered steps with gates/artifacts |
| `list_failed_runs(limit=20)` | Dict | Failed runs with error reasons |

### Response Formats

**get_run_summary:**
```python
{
    "run_id": "IN-ABC123-run-2026-01-20",
    "playbook_id": "courier-integration-v0.1",
    "status": "completed",
    "steps_count": 3,
    "events_count": 15,
    "artifacts_count": 3,
    "started_at": "2026-01-20T10:00:00Z",
    "ended_at": "2026-01-20T10:05:00Z"
}
```

**get_step_timeline:**
```python
{
    "run_id": "IN-ABC123-run-2026-01-20",
    "steps": [
        {
            "step_id": "step_1_intake",
            "agent_id": "intake-agent",
            "status": "completed",
            "started_at": "2026-01-20T10:00:00Z",
            "ended_at": "2026-01-20T10:01:00Z",
            "gate_results": [
                {"gate_name": "profile_exists", "result": True, "reason": "Found"}
            ],
            "artifact_ids": ["artifact_001"]
        }
    ]
}
```

**list_failed_runs:**
```python
{
    "runs": [
        {
            "run_id": "IN-XYZ789-run-2026-01-20",
            "playbook_id": "courier-integration-v0.1",
            "failed_step": "step_2_detection",
            "reason": "Gate check failed: missing profile",
            "ended_at": "2026-01-20T11:02:00Z"
        }
    ]
}
```

---

## Performance

Tested with 500-event runs:
- `get_run_summary`: <100ms
- `get_step_timeline`: <200ms
- `list_failed_runs`: <500ms

All queries leverage indexes for efficient access.

---

## See Also

- [ADR-003-telemetry-storage.md](../docs/adr/ADR-003-telemetry-storage.md) - Architecture decision
- [telemetry.event.schema.json](telemetry.event.schema.json) - Event validation schema
- [telemetry_store.py](../runtime/telemetry_store.py) - Implementation
