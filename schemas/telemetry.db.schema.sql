-- ProcessOS Telemetry Database Schema (SQLite)
-- Sprint 2: Layer 3 Persistence
-- Last Updated: 2026-01-20

-- Enable foreign keys for integrity
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: runs
-- Purpose: Top-level execution record for each playbook run
-- ============================================================================
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  playbook_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
    -- Status values: running, completed, failed
  started_at TEXT NOT NULL,
    -- ISO 8601 timestamp
  ended_at TEXT,
    -- ISO 8601 timestamp, NULL if still running
  state_hash TEXT,
    -- SHA256 of final state.json for integrity
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_status_ended_at
  ON runs(status, ended_at);


-- ============================================================================
-- TABLE: steps
-- Purpose: Record each step execution within a run
-- ============================================================================
CREATE TABLE IF NOT EXISTS steps (
  step_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  agent_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
    -- Status values: pending, started, completed, failed
  started_at TEXT,
  ended_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (step_id, run_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_steps_run_id_started_at
  ON steps(run_id, started_at);


-- ============================================================================
-- TABLE: events
-- Purpose: Immutable telemetry events (critical + high + normal)
-- Design: INSERT-only, never UPDATE/DELETE
-- ============================================================================
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT,
    -- Reference to step (may be NULL for run-level events)
  agent_id TEXT,
    -- Agent identifier (may be NULL for non-agent events)
  event_type TEXT NOT NULL,
    -- run_started, step_started, gate_passed, gate_failed, step_completed, error, etc.
  criticality TEXT NOT NULL,
    -- critical, high, normal
  timestamp TEXT NOT NULL,
    -- ISO 8601 timestamp when event occurred
  data JSON,
    -- Event-specific payload (JSON): gate_name, gate_result, gate_reason, error_message, etc.
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (step_id, run_id) REFERENCES steps(step_id, run_id) ON DELETE CASCADE
);

-- Query indexes for typical access patterns
CREATE INDEX IF NOT EXISTS idx_events_run_id_timestamp
  ON events(run_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_events_run_id_step_id_timestamp
  ON events(run_id, step_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_events_run_id_event_type_timestamp
  ON events(run_id, event_type, timestamp);

CREATE INDEX IF NOT EXISTS idx_events_criticality_run_id
  ON events(criticality, run_id);


-- ============================================================================
-- TABLE: artifacts
-- Purpose: Record artifacts generated during run (immutable references)
-- Design: By reference (path + sha256), not content
-- ============================================================================
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  artifact_kind TEXT,
    -- Type of artifact: courier_intake_report, detection_report, api_mapping, etc.
  path TEXT NOT NULL,
    -- Relative path to artifact file (e.g., "artifacts/artifact_001.md")
  sha256 TEXT NOT NULL,
    -- SHA256 hash of artifact content for integrity
  size_bytes INTEGER,
  content_type TEXT DEFAULT 'text/markdown',
  created_at TEXT NOT NULL,
    -- ISO 8601 timestamp when artifact created
  created_by_step TEXT,
    -- Step ID that created this artifact
  created_at_sys TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (created_by_step, run_id) REFERENCES steps(step_id, run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_id_kind
  ON artifacts(run_id, artifact_kind);

CREATE INDEX IF NOT EXISTS idx_artifacts_sha256
  ON artifacts(sha256);


-- ============================================================================
-- INTEGRITY CONSTRAINTS
-- ============================================================================

-- Verify schema integrity on database connection
PRAGMA integrity_check;
