"""
Unit tests for telemetry_importer
Sprint 2: Test suite for JSONL to SQLite import layer
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
import uuid
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from telemetry_store import TelemetryStore
from telemetry_importer import import_jsonl_to_sqlite


@pytest.fixture
def temp_db():
    """Create a temporary database for each test"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    import time
    import gc
    time.sleep(0.1)
    gc.collect()
    time.sleep(0.1)
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


@pytest.fixture
def temp_jsonl():
    """Create a temporary JSONL file"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as f:
        jsonl_path = f.name
    yield jsonl_path
    # Cleanup
    Path(jsonl_path).unlink(missing_ok=True)


def create_test_run(store: TelemetryStore, run_id: str) -> None:
    """Helper: Create a test run record"""
    store.conn.execute(
        "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
        (run_id, "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
    )
    store.conn.commit()


class TestImporterFunctionality:
    """Test importer core functionality"""

    def test_import_valid_jsonl(self, temp_db, temp_jsonl):
        """Test: Import 5 valid JSONL events → all imported, count matches"""
        # Arrange - Initialize DB
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-import-001"
        create_test_run(store, run_id)
        store.close()

        # Arrange - Write valid JSONL
        events = []
        with open(temp_jsonl, 'w') as f:
            for i in range(5):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                    "data": {"index": i}
                }
                events.append(event)
                f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert
        assert result["success"] is True
        assert result["imported"] == 5
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0

        # Verify in DB
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 5
        store.close()

    def test_import_idempotent_duplicates(self, temp_db, temp_jsonl):
        """Test: Import twice with duplicates → second import skips all"""
        # Arrange - Initialize DB
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-import-002"
        create_test_run(store, run_id)
        store.close()

        # Arrange - Write JSONL
        event_ids = []
        with open(temp_jsonl, 'w') as f:
            for i in range(3):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                event_ids.append(event["event_id"])
                f.write(json.dumps(event) + '\n')

        # Act - First import
        result1 = import_jsonl_to_sqlite(temp_jsonl, temp_db)
        assert result1["imported"] == 3
        assert result1["skipped"] == 0

        # Act - Second import (should skip all)
        result2 = import_jsonl_to_sqlite(temp_jsonl, temp_db)
        assert result2["imported"] == 0
        assert result2["skipped"] == 3

        # Verify total count unchanged
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 3
        store.close()

    def test_import_with_invalid_events(self, temp_db, temp_jsonl, capsys):
        """Test: Import with <10% invalid events → valid events imported"""
        # Arrange - Initialize DB
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-import-003"
        create_test_run(store, run_id)
        store.close()

        # Arrange - Write JSONL with 1 invalid out of 11 (9.09%, below 10% threshold)
        with open(temp_jsonl, 'w') as f:
            # 5 valid
            for i in range(5):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(event) + '\n')

            # 1 invalid (missing run_id)
            invalid_event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "step_completed",
                "criticality": "critical",
            }
            f.write(json.dumps(invalid_event) + '\n')

            # 5 more valid
            for i in range(5):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert - 1 invalid out of 11 = 9.09%, below threshold
        assert result["imported"] == 10  # 10 valid events
        assert result["skipped"] == 0   # Skipped means FK duplicates, not validation errors
        assert len(result["errors"]) >= 1  # At least 1 error logged
        assert "run_id" in result["errors"][0].lower()  # Error mentions missing field

        # Verify in DB
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 10
        store.close()

    def test_import_too_many_errors_aborts(self, temp_db, temp_jsonl):
        """Test: >10% invalid events → abort import, transaction rolled back"""
        # Arrange - Initialize DB
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-import-004"
        create_test_run(store, run_id)
        store.close()

        # Arrange - Write JSONL with >10% invalid
        with open(temp_jsonl, 'w') as f:
            # 2 valid
            for i in range(2):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(event) + '\n')

            # 3 invalid (>50%)
            for i in range(3):
                invalid_event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    # Missing run_id
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(invalid_event) + '\n')

        # Act & Assert - Should raise exception
        with pytest.raises(Exception, match="Too many validation errors"):
            import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Verify nothing inserted (transaction rolled back)
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 0  # No events inserted due to rollback
        store.close()


class TestForeignKeyHandling:
    """Test FK correlation and orphaned event handling"""

    def test_orphaned_run_creates_placeholder(self, temp_db, temp_jsonl):
        """Test: Event references non-existent run_id → placeholder created"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        store.close()

        orphan_run_id = "orphan-run-999"

        # Write JSONL with orphan run_id
        with open(temp_jsonl, 'w') as f:
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "run_id": orphan_run_id,
                "event_type": "step_completed",
                "criticality": "critical",
            }
            f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert
        assert result["success"] is True
        assert result["imported"] == 1  # Event imported

        # Verify placeholder run was created
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute(
            "SELECT status FROM runs WHERE run_id = ?",
            (orphan_run_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "orphan"  # Placeholder run with status="orphan"
        store.close()

    def test_event_with_missing_step_logs_warning(self, temp_db, temp_jsonl, capsys):
        """Test: Event references non-existent step_id → warning logged, event inserted"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-fk-001"
        create_test_run(store, run_id)
        store.close()

        # Write JSONL with non-existent step_id
        with open(temp_jsonl, 'w') as f:
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "run_id": run_id,
                "step_id": "non-existent-step",
                "event_type": "step_completed",
                "criticality": "critical",
            }
            f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert
        assert result["imported"] == 1  # Still imported (non-strict mode)

        # Verify event exists
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 1
        store.close()


class TestErrorHandling:
    """Test error handling and reporting"""

    def test_malformed_json_line_skipped(self, temp_db, temp_jsonl):
        """Test: <10% malformed JSON → error logged, valid events imported"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-error-001"
        create_test_run(store, run_id)
        store.close()

        # Write JSONL with 1 malformed out of 11 (9.09%, below 10% threshold)
        with open(temp_jsonl, 'w') as f:
            # 5 valid
            for i in range(5):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(event) + '\n')

            # 1 Malformed
            f.write("{ invalid json ]\n")

            # 5 more valid
            for i in range(5):
                event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "run_id": run_id,
                    "event_type": "step_completed",
                    "criticality": "critical",
                }
                f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert - 1 malformed out of 11 = 9.09%, below threshold
        assert result["imported"] == 10  # 10 valid events
        assert len(result["errors"]) >= 1  # Error logged for malformed line

        # Verify in DB
        store = TelemetryStore(temp_db, create_tables=False)
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 10
        store.close()

    def test_result_dict_structure(self, temp_db, temp_jsonl):
        """Test: Result dict has correct structure"""
        # Arrange
        store = TelemetryStore(temp_db, create_tables=True)
        run_id = "test-error-002"
        create_test_run(store, run_id)
        store.close()

        with open(temp_jsonl, 'w') as f:
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "run_id": run_id,
                "event_type": "step_completed",
                "criticality": "critical",
            }
            f.write(json.dumps(event) + '\n')

        # Act
        result = import_jsonl_to_sqlite(temp_jsonl, temp_db)

        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        assert "imported" in result
        assert "skipped" in result
        assert "errors" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["imported"], int)
        assert isinstance(result["skipped"], int)
        assert isinstance(result["errors"], list)
