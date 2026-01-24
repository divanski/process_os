"""
Unit tests for TelemetryStore
Sprint 2: Test suite for SQLite persistence layer
"""

import pytest
import json
import tempfile
import threading
from pathlib import Path
from datetime import datetime
import uuid

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from telemetry_store import TelemetryStore


@pytest.fixture
def temp_db():
    """Create a temporary database for each test"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup - close any remaining connections first
    import time
    import gc
    time.sleep(0.1)  # Allow connection to close
    gc.collect()  # Force garbage collection to release SQLite connections
    time.sleep(0.1)  # Wait for resources to be released
    # Retry delete in case of Windows file locks
    max_retries = 5
    for attempt in range(max_retries):
        try:
            Path(db_path).unlink(missing_ok=True)
            break
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(0.1)
            else:
                pass  # Silently fail on last attempt


def create_test_run(store: TelemetryStore, run_id: str) -> None:
    """Helper: Create a test run record (required for FK constraints)"""
    store.conn.execute(
        """
        INSERT INTO runs (run_id, playbook_id, status, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (run_id, "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
    )
    store.conn.commit()


def create_test_step(store: TelemetryStore, step_id: str, run_id: str) -> None:
    """Helper: Create a test step record (required for FK constraints on events)"""
    store.conn.execute(
        """
        INSERT INTO steps (step_id, run_id, status, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (step_id, run_id, "running", datetime.utcnow().isoformat() + "Z")
    )
    store.conn.commit()


@pytest.fixture
def valid_event():
    """Create a valid telemetry event"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "run_id": "test-run-001",
        "event_type": "run_started",
        "criticality": "critical",
        "data": {}
    }


class TestDatabaseInitialization:
    """Test database creation and table structure"""

    def test_database_initialization(self, temp_db):
        """Test: Database initialization creates all tables and indexes"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Act
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        # Assert
        assert "runs" in tables, "runs table not created"
        assert "steps" in tables, "steps table not created"
        assert "events" in tables, "events table not created"
        assert "artifacts" in tables, "artifacts table not created"

        # Verify indexes
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        assert len(indexes) >= 4, "Expected at least 4 indexes"

        # Cleanup
        store.close()

    def test_database_file_exists(self, temp_db):
        """Test: Database file is created on disk"""
        # Arrange
        # Note: NamedTemporaryFile creates with delete=False, so file exists

        # Act
        store = TelemetryStore(temp_db, create_tables=True)

        # Assert
        assert Path(temp_db).exists(), "Database file not created"
        store.close()  # Close connection before fixture cleanup


class TestValidEventPersistence:
    """Test valid event storage"""

    def test_valid_event_persistence(self, temp_db, valid_event):
        """Test: Valid event persists to events table"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        create_test_run(store, valid_event["run_id"])

        # Act
        store.persist_event(valid_event)

        # Assert
        cursor = store.conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (valid_event["event_id"],)
        )
        row = cursor.fetchone()
        assert row is not None, "Event not found in database"
        assert row["run_id"] == valid_event["run_id"]
        assert row["event_type"] == valid_event["event_type"]
        assert row["criticality"] == valid_event["criticality"]

        # Cleanup
        store.close()

    def test_event_with_optional_fields(self, temp_db):
        """Test: Event with optional fields (step_id, agent_id) persists correctly"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-run-002"
        step_id = "step_1_intake"
        create_test_run(store, run_id)
        create_test_step(store, step_id, run_id)
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": run_id,
            "step_id": step_id,
            "agent_id": "intake-agent-v1",
            "event_type": "step_started",
            "criticality": "critical",
            "data": {}
        }

        # Act
        store.persist_event(event)

        # Assert
        cursor = store.conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event["event_id"],)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["step_id"] == "step_1_intake"
        assert row["agent_id"] == "intake-agent-v1"

        # Cleanup - close before fixture cleanup to release file lock
        store.close()

    def test_event_with_data_payload(self, temp_db):
        """Test: Event with JSON data persists correctly"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-run-003"
        create_test_run(store, run_id)
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": run_id,
            "event_type": "gate_passed",
            "criticality": "critical",
            "data": {
                "gate_name": "courier_profile_exists",
                "gate_result": True,
                "gate_reason": "File found at path"
            }
        }

        # Act
        store.persist_event(event)

        # Assert
        cursor = store.conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event["event_id"],)
        )
        row = cursor.fetchone()
        assert row is not None
        stored_data = json.loads(row["data"])
        assert stored_data["gate_name"] == "courier_profile_exists"
        assert stored_data["gate_result"] is True

        # Cleanup - close before fixture cleanup to release file lock
        store.close()


class TestInvalidEventRejection:
    """Test invalid event rejection"""

    def test_invalid_event_missing_run_id(self, temp_db):
        """Test: Event missing run_id is rejected"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            # Missing run_id
            "event_type": "run_started",
            "criticality": "critical",
            "data": {}
        }

        # Act & Assert
        with pytest.raises(ValueError, match="validation failed"):
            store.persist_event(event)

        # Verify nothing was inserted
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 0, "Invalid event was persisted"

        # Cleanup
        store.close()

    def test_invalid_event_missing_criticality(self, temp_db):
        """Test: Event missing criticality is rejected"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": "test-run-004",
            "event_type": "run_started",
            # Missing criticality
            "data": {}
        }

        # Act & Assert
        with pytest.raises(ValueError, match="validation failed"):
            store.persist_event(event)

        # Cleanup
        store.close()

    def test_invalid_event_wrong_type(self, temp_db):
        """Test: Event with invalid event_type is rejected"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "run_id": "test-run-005",
            "event_type": "invalid_type",  # Not in enum
            "criticality": "critical",
            "data": {}
        }

        # Act & Assert
        with pytest.raises(ValueError, match="validation failed"):
            store.persist_event(event)

        # Cleanup
        store.close()


class TestConcurrentPersistence:
    """Test thread-safe concurrent writes"""

    def test_concurrent_persistence(self, temp_db):
        """Test: Concurrent writes from multiple threads preserve integrity"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        create_test_run(store, "test-concurrent-run")
        num_threads = 4
        events_per_thread = 25
        total_events = num_threads * events_per_thread

        def insert_events(thread_id: int):
            """Helper to insert events from thread"""
            for i in range(events_per_thread):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": "test-concurrent-run",
                    "event_type": "step_completed",
                    "criticality": "normal",
                    "data": {"thread_id": thread_id, "index": i}
                }
                store.persist_event(event)

        # Act
        threads = []
        for t_id in range(num_threads):
            t = threading.Thread(target=insert_events, args=(t_id,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Assert - verify all events persisted
        cursor = store.conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ?",
            ("test-concurrent-run",)
        )
        count = cursor.fetchone()[0]
        assert count == total_events, f"Expected {total_events} events, got {count}"

        # Verify no duplicates
        cursor = store.conn.execute(
            "SELECT COUNT(DISTINCT event_id) FROM events WHERE run_id = ?",
            ("test-concurrent-run",)
        )
        distinct_count = cursor.fetchone()[0]
        assert distinct_count == total_events, "Duplicate event_ids detected"

        # Cleanup - close before fixture cleanup to release file lock
        store.close()

    def test_no_lost_events_under_concurrent_load(self, temp_db):
        """Test: No events lost under concurrent load"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        create_test_run(store, "test-load-run")
        num_threads = 8
        events_per_thread = 50
        total_expected = num_threads * events_per_thread

        def rapid_insert(thread_id: int):
            """Rapidly insert events"""
            for i in range(events_per_thread):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": "test-load-run",
                    "event_type": "artifact_registered",
                    "criticality": "critical",
                    "data": {}
                }
                store.persist_event(event)

        # Act
        threads = [threading.Thread(target=rapid_insert, args=(t_id,))
                   for t_id in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == total_expected, f"Lost events: expected {total_expected}, got {count}"

        # Cleanup - close before fixture cleanup to release file lock
        store.close()


class TestDatabaseIntegrity:
    """Test database constraint and integrity"""

    def test_duplicate_event_id_rejected(self, temp_db, valid_event):
        """Test: Attempting to insert duplicate event_id is rejected"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        create_test_run(store, valid_event["run_id"])

        # Act - Insert first event
        store.persist_event(valid_event)

        # Act - Try to insert duplicate
        with pytest.raises(ValueError, match="Database integrity error"):
            store.persist_event(valid_event)

        # Cleanup
        store.close()


# =============================================================================
# S2-003: Query API Tests
# =============================================================================

class TestGetRunSummary:
    """Test get_run_summary query method"""

    def test_get_run_summary_returns_accurate_counts(self, temp_db):
        """Test: get_run_summary returns accurate counts for events, steps, artifacts"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-summary-run"

        # Create run
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, "test-playbook", "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:05:00Z")
        )

        # Create 2 steps
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("step_1", run_id, "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:02:00Z")
        )
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("step_2", run_id, "completed", "2026-01-20T10:02:00Z", "2026-01-20T10:05:00Z")
        )

        # Create 5 events
        for i in range(5):
            store.conn.execute(
                "INSERT INTO events (event_id, run_id, event_type, criticality, timestamp) VALUES (?, ?, ?, ?, ?)",
                (f"event-{i}", run_id, "step_completed", "critical", f"2026-01-20T10:0{i}:00Z")
            )

        # Create 1 artifact
        store.conn.execute(
            "INSERT INTO artifacts (artifact_id, run_id, path, sha256, created_at) VALUES (?, ?, ?, ?, ?)",
            ("artifact-1", run_id, "/artifacts/test.md", "abc123", "2026-01-20T10:03:00Z")
        )
        store.conn.commit()

        # Act
        result = store.get_run_summary(run_id)

        # Assert
        assert result is not None
        assert result["run_id"] == run_id
        assert result["playbook_id"] == "test-playbook"
        assert result["status"] == "completed"
        assert result["steps_count"] == 2
        assert result["events_count"] == 5
        assert result["artifacts_count"] == 1
        assert result["started_at"] == "2026-01-20T10:00:00Z"
        assert result["ended_at"] == "2026-01-20T10:05:00Z"

        store.close()

    def test_get_run_summary_nonexistent_returns_none(self, temp_db):
        """Test: get_run_summary returns None for nonexistent run_id"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Act
        result = store.get_run_summary("nonexistent-run-id")

        # Assert
        assert result is None

        store.close()


class TestGetStepTimeline:
    """Test get_step_timeline query method"""

    def test_get_step_timeline_ordered_with_gates(self, temp_db):
        """Test: get_step_timeline returns steps in order with gate results"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-timeline-run"

        # Create run
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            (run_id, "test-playbook", "completed", "2026-01-20T10:00:00Z")
        )

        # Create 3 steps in order
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, agent_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("step_1_intake", run_id, "intake-agent", "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:01:00Z")
        )
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, agent_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("step_2_detect", run_id, "detect-agent", "completed", "2026-01-20T10:01:00Z", "2026-01-20T10:02:00Z")
        )
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, agent_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("step_3_report", run_id, "report-agent", "completed", "2026-01-20T10:02:00Z", "2026-01-20T10:03:00Z")
        )

        # Add gate events for each step
        store.conn.execute(
            "INSERT INTO events (event_id, run_id, step_id, event_type, criticality, timestamp, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("gate-1", run_id, "step_1_intake", "gate_passed", "critical", "2026-01-20T10:00:30Z",
             json.dumps({"gate_name": "profile_exists", "gate_result": True, "gate_reason": "Found"}))
        )
        store.conn.execute(
            "INSERT INTO events (event_id, run_id, step_id, event_type, criticality, timestamp, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("gate-2", run_id, "step_2_detect", "gate_passed", "critical", "2026-01-20T10:01:30Z",
             json.dumps({"gate_name": "detection_valid", "gate_result": True, "gate_reason": "Valid"}))
        )

        # Add artifact for step_1 to test artifact_ids population
        store.conn.execute(
            "INSERT INTO artifacts (artifact_id, run_id, path, sha256, created_at, created_by_step) VALUES (?, ?, ?, ?, ?, ?)",
            ("artifact-intake-1", run_id, "/artifacts/intake_report.md", "abc123", "2026-01-20T10:00:45Z", "step_1_intake")
        )
        store.conn.commit()

        # Act
        result = store.get_step_timeline(run_id)

        # Assert
        assert result is not None
        assert result["run_id"] == run_id
        assert len(result["steps"]) == 3

        # Check order (by started_at)
        assert result["steps"][0]["step_id"] == "step_1_intake"
        assert result["steps"][1]["step_id"] == "step_2_detect"
        assert result["steps"][2]["step_id"] == "step_3_report"

        # Check gate results
        assert len(result["steps"][0]["gate_results"]) == 1
        assert result["steps"][0]["gate_results"][0]["gate_name"] == "profile_exists"
        assert result["steps"][0]["gate_results"][0]["result"] is True

        # Check artifact_ids populated for step_1
        assert "artifact-intake-1" in result["steps"][0]["artifact_ids"]

        store.close()

    def test_get_step_timeline_nonexistent_returns_none(self, temp_db):
        """Test: get_step_timeline returns None for nonexistent run_id"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Act
        result = store.get_step_timeline("nonexistent-run-id")

        # Assert
        assert result is None

        store.close()


class TestListFailedRuns:
    """Test list_failed_runs query method"""

    def test_list_failed_runs_empty_when_none(self, temp_db):
        """Test: list_failed_runs returns empty list when no failed runs"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Create 2 successful runs
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-1", "playbook", "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:05:00Z")
        )
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-2", "playbook", "completed", "2026-01-20T11:00:00Z", "2026-01-20T11:05:00Z")
        )
        store.conn.commit()

        # Act
        result = store.list_failed_runs()

        # Assert
        assert result is not None
        assert "runs" in result
        assert len(result["runs"]) == 0

        store.close()

    def test_list_failed_runs_returns_correct_runs(self, temp_db):
        """Test: list_failed_runs returns failed runs with correct info"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Create 1 successful run
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-success", "playbook", "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:05:00Z")
        )

        # Create 1 failed run
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-failed", "playbook", "failed", "2026-01-20T11:00:00Z", "2026-01-20T11:02:00Z")
        )

        # Create step for FK constraint
        store.conn.execute(
            "INSERT INTO steps (step_id, run_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("step_2", "run-failed", "failed", "2026-01-20T11:01:00Z")
        )

        # Add error event to failed run
        store.conn.execute(
            "INSERT INTO events (event_id, run_id, step_id, event_type, criticality, timestamp, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("error-1", "run-failed", "step_2", "error", "critical", "2026-01-20T11:01:30Z",
             json.dumps({"error_message": "Gate check failed: missing profile"}))
        )
        store.conn.commit()

        # Act
        result = store.list_failed_runs()

        # Assert
        assert result is not None
        assert len(result["runs"]) == 1
        assert result["runs"][0]["run_id"] == "run-failed"
        assert result["runs"][0]["playbook_id"] == "playbook"
        assert result["runs"][0]["reason"] == "Gate check failed: missing profile"
        assert result["runs"][0]["failed_step"] == "step_2"
        assert result["runs"][0]["ended_at"] == "2026-01-20T11:02:00Z"

        store.close()

    def test_list_failed_runs_respects_limit(self, temp_db):
        """Test: list_failed_runs respects limit parameter"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Create 5 failed runs
        for i in range(5):
            store.conn.execute(
                "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
                (f"run-failed-{i}", "playbook", "failed", f"2026-01-20T1{i}:00:00Z", f"2026-01-20T1{i}:05:00Z")
            )
        store.conn.commit()

        # Act
        result = store.list_failed_runs(limit=3)

        # Assert
        assert len(result["runs"]) == 3

        store.close()

    def test_list_failed_runs_ordered_by_ended_at_desc(self, temp_db):
        """Test: list_failed_runs returns runs ordered by ended_at descending"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)

        # Create 3 failed runs with different end times
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-old", "playbook", "failed", "2026-01-20T09:00:00Z", "2026-01-20T09:05:00Z")
        )
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-newest", "playbook", "failed", "2026-01-20T12:00:00Z", "2026-01-20T12:05:00Z")
        )
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            ("run-middle", "playbook", "failed", "2026-01-20T10:00:00Z", "2026-01-20T10:05:00Z")
        )
        store.conn.commit()

        # Act
        result = store.list_failed_runs()

        # Assert - should be ordered newest first
        assert result["runs"][0]["run_id"] == "run-newest"
        assert result["runs"][1]["run_id"] == "run-middle"
        assert result["runs"][2]["run_id"] == "run-old"

        store.close()


class TestQueryPerformance:
    """Test query performance requirements"""

    def test_query_performance_under_1_second(self, temp_db):
        """Test: All query methods complete in <1s for 500-event run"""
        import time

        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-perf-run"

        # Create run with 500 events
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, "test-playbook", "completed", "2026-01-20T10:00:00Z", "2026-01-20T10:30:00Z")
        )

        # Create 5 steps
        for i in range(5):
            store.conn.execute(
                "INSERT INTO steps (step_id, run_id, status, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
                (f"step_{i}", run_id, "completed", f"2026-01-20T10:0{i}:00Z", f"2026-01-20T10:0{i+1}:00Z")
            )

        # Create 500 events
        for i in range(500):
            store.conn.execute(
                "INSERT INTO events (event_id, run_id, step_id, event_type, criticality, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (f"event-{i}", run_id, f"step_{i % 5}", "step_completed", "normal", f"2026-01-20T10:{i//60:02d}:{i%60:02d}Z")
            )
        store.conn.commit()

        # Act & Assert - get_run_summary
        start = time.time()
        result1 = store.get_run_summary(run_id)
        elapsed1 = time.time() - start
        assert elapsed1 < 1.0, f"get_run_summary took {elapsed1:.2f}s (>1s)"
        assert result1 is not None

        # Act & Assert - get_step_timeline
        start = time.time()
        result2 = store.get_step_timeline(run_id)
        elapsed2 = time.time() - start
        assert elapsed2 < 1.0, f"get_step_timeline took {elapsed2:.2f}s (>1s)"
        assert result2 is not None

        # Act & Assert - list_failed_runs
        start = time.time()
        result3 = store.list_failed_runs()
        elapsed3 = time.time() - start
        assert elapsed3 < 1.0, f"list_failed_runs took {elapsed3:.2f}s (>1s)"
        assert result3 is not None

        store.close()
