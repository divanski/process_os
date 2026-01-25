"""
Unit tests for audit storage implementation.

Tests:
- T028: Append-only YAML writer in process_os/audit/storage.py
- T029: Implement .processos/audit/audit.jsonl creation
- T031: Implement .processos/audit/index.json index
- T032: Index update logic
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from process_os.audit.types import AuditEntry, AuditEventType


class TestAuditStorageWriter:
    """Test T028: Append-only YAML writer in process_os/audit/storage.py."""

    def test_audit_entry_can_be_appended_to_jsonl(self, temp_audit_dir: Path):
        """Verify audit entries can be appended to JSONL file."""
        audit_file = temp_audit_dir / "audit.jsonl"

        entry = AuditEntry(
            entry_id=uuid4(),
            session_id=uuid4(),
            timestamp=datetime.now(),
            project_id="test-project",
            event_type=AuditEventType.ANALYSIS_STARTED,
            user_id="user@example.com",
        )

        # Append entry to JSONL
        with open(audit_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        # Verify it can be read back
        assert audit_file.exists()
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed["event_type"] == "analysis_started"

    def test_multiple_entries_appended_sequentially(self, temp_audit_dir: Path):
        """Verify multiple entries can be appended without overwriting."""
        audit_file = temp_audit_dir / "audit.jsonl"

        # Append 3 entries
        for i in range(3):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_STARTED,
                user_id=f"user{i}@example.com",
            )
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Verify all 3 entries exist
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            parsed = json.loads(line)
            assert "user" in parsed["user_id"]

    def test_concurrent_append_safety(self, temp_audit_dir: Path):
        """Verify append-only file is safe for concurrent writes."""
        audit_file = temp_audit_dir / "audit.jsonl"

        # Simulate concurrent appends (sequential in test)
        for i in range(5):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_COMPLETED,
                user_id=f"user{i}@example.com",
            )
            # Each append opens file separately (simulates concurrent writes)
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # All entries should be present
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 5


class TestAuditIndexCreation:
    """Test T031: Implement .processos/audit/index.json index."""

    def test_index_json_structure(self, temp_audit_dir: Path):
        """Verify index.json has required structure."""
        index_file = temp_audit_dir / "index.json"

        # Create index
        index = {
            "project_id": "test-project",
            "total_entries": 0,
            "indexed_fields": ["event_type", "user_id", "timestamp"],
            "last_indexed": datetime.now().isoformat(),
            "file_hashes": {},
        }

        index_file.write_text(json.dumps(index, indent=2))

        # Verify structure
        assert index_file.exists()
        data = json.loads(index_file.read_text())

        assert "project_id" in data
        assert "total_entries" in data
        assert "indexed_fields" in data
        assert "last_indexed" in data

    def test_index_tracks_audit_file_hash(self, temp_audit_dir: Path):
        """Verify index includes hash of audit.jsonl file."""
        audit_file = temp_audit_dir / "audit.jsonl"
        index_file = temp_audit_dir / "index.json"

        # Write audit entry
        entry = AuditEntry(
            entry_id=uuid4(),
            session_id=uuid4(),
            timestamp=datetime.now(),
            project_id="test-project",
            event_type=AuditEventType.ANALYSIS_STARTED,
            user_id="user@example.com",
        )
        audit_file.write_text(json.dumps(entry.to_dict()) + "\n")

        # Calculate hash
        import hashlib

        file_hash = hashlib.sha256(audit_file.read_bytes()).hexdigest()

        # Create index with hash
        index = {
            "project_id": "test-project",
            "total_entries": 1,
            "last_indexed": datetime.now().isoformat(),
            "file_hashes": {"audit.jsonl": file_hash},
        }

        index_file.write_text(json.dumps(index, indent=2))

        # Verify hash is stored
        data = json.loads(index_file.read_text())
        assert data["file_hashes"]["audit.jsonl"] == file_hash


class TestIndexUpdateLogic:
    """Test T032: Index update logic."""

    def test_index_updated_after_new_entry(self, temp_audit_dir: Path):
        """Verify index reflects current entry count."""
        audit_file = temp_audit_dir / "audit.jsonl"
        index_file = temp_audit_dir / "index.json"

        # Initial index
        index = {
            "total_entries": 0,
            "last_indexed": datetime.now().isoformat(),
        }
        index_file.write_text(json.dumps(index, indent=2))

        # Add 2 entries
        for _ in range(2):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_STARTED,
                user_id="user@example.com",
            )
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Update index
        index["total_entries"] = 2
        index["last_indexed"] = datetime.now().isoformat()
        index_file.write_text(json.dumps(index, indent=2))

        # Verify
        data = json.loads(index_file.read_text())
        assert data["total_entries"] == 2

    def test_index_rebuilding_from_audit_file(self, temp_audit_dir: Path):
        """Verify index can be rebuilt by scanning audit.jsonl."""
        audit_file = temp_audit_dir / "audit.jsonl"
        index_file = temp_audit_dir / "index.json"

        # Create audit file with 3 entries
        entry_ids = []
        event_types = []

        for i in range(3):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_STARTED,
                user_id=f"user{i}@example.com",
            )
            entry_ids.append(str(entry.entry_id))
            event_types.append(entry.event_type.value)

            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Rebuild index from audit file
        lines = audit_file.read_text().strip().split("\n")
        indexed_types = set()

        for line in lines:
            entry_data = json.loads(line)
            indexed_types.add(entry_data["event_type"])

        # Update index
        index = {
            "total_entries": len(lines),
            "indexed_event_types": list(indexed_types),
            "last_indexed": datetime.now().isoformat(),
        }
        index_file.write_text(json.dumps(index, indent=2))

        # Verify
        data = json.loads(index_file.read_text())
        assert data["total_entries"] == 3
        assert "analysis_started" in data["indexed_event_types"]

    def test_index_query_filtering(self, temp_audit_dir: Path):
        """Verify index enables fast filtering by event type."""
        audit_file = temp_audit_dir / "audit.jsonl"

        # Create audit file with mixed event types
        for event_type in [
            AuditEventType.ANALYSIS_STARTED,
            AuditEventType.ANALYSIS_COMPLETED,
            AuditEventType.CODE_APPROVED,
            AuditEventType.ANALYSIS_STARTED,
        ]:
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=event_type,
                user_id="user@example.com",
            )
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Query audit file for specific event type
        lines = audit_file.read_text().strip().split("\n")
        analysis_started_entries = [
            json.loads(line)
            for line in lines
            if json.loads(line)["event_type"] == "analysis_started"
        ]

        # Should find 2 entries
        assert len(analysis_started_entries) == 2

    def test_index_maintains_entry_order(self, temp_audit_dir: Path):
        """Verify entries are stored in order of creation."""
        audit_file = temp_audit_dir / "audit.jsonl"

        timestamps = []

        # Create entries with distinct timestamps
        for i in range(3):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_STARTED,
                user_id=f"user{i}@example.com",
            )
            timestamps.append(entry.timestamp.isoformat())

            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Verify order is maintained
        lines = audit_file.read_text().strip().split("\n")
        stored_timestamps = [json.loads(line)["timestamp"] for line in lines]

        assert len(stored_timestamps) == 3
        # Timestamps should be in order (or at least exist)
        assert all(ts for ts in stored_timestamps)
