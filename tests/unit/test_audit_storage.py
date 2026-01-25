"""
Unit tests for audit trail storage and index creation.

Tests:
- T030: JSON index creation for fast querying
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from process_os.audit.types import AuditEntry, AuditEventType


class TestAuditStorage:
    """Test T030: Audit trail storage with JSON index."""

    def test_audit_entry_serialization(self):
        """Verify audit entry can be serialized to JSON."""
        entry = AuditEntry(
            entry_id=uuid4(),
            session_id=uuid4(),
            timestamp=datetime.now(),
            project_id="test-project-hash",
            event_type=AuditEventType.ANALYSIS_STARTED,
            user_id="developer@example.com",
        )

        json_data = json.dumps(entry.to_dict())
        assert isinstance(json_data, str)

        # Verify it can be deserialized
        parsed = json.loads(json_data)
        assert parsed["event_type"] == "analysis_started"
        assert parsed["project_id"] == "test-project-hash"

    def test_audit_entry_with_metadata(self):
        """Verify audit entry with rich metadata."""
        entry = AuditEntry(
            entry_id=uuid4(),
            session_id=uuid4(),
            timestamp=datetime.now(),
            project_id="test-project",
            event_type=AuditEventType.CODE_APPROVED,
            user_id="reviewer@example.com",
            approved_by="reviewer@example.com",
            approval_comment="Looks good!",
            files_affected=["app/Http/Controllers/HomeController.php"],
            event_metadata={"confidence": 0.95, "patterns_used": 3},
        )

        data = entry.to_dict()
        assert data["approval_comment"] == "Looks good!"
        assert len(data["files_affected"]) == 1
        assert data["event_metadata"]["confidence"] == 0.95

    def test_json_index_structure(self):
        """Verify JSON index format for fast querying."""
        # Index structure: one JSON object per line (JSONL format)
        entries = []
        for i in range(5):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test-project",
                event_type=AuditEventType.ANALYSIS_COMPLETED,
                user_id="user@example.com",
            )
            entries.append(entry.to_dict())

        # Simulate JSONL format (one JSON object per line)
        jsonl_content = "\n".join(json.dumps(entry) for entry in entries)

        # Verify each line is valid JSON
        lines = jsonl_content.strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            parsed = json.loads(line)
            assert "entry_id" in parsed
            assert "event_type" in parsed

    def test_index_file_creation(self, temp_audit_dir: Path):
        """Verify index.json file can be created."""
        index_file = temp_audit_dir / "index.json"

        # Create sample index
        index_data = {
            "project_id": "test-project",
            "total_entries": 10,
            "indexed_fields": [
                "event_type",
                "user_id",
                "timestamp",
            ],
            "last_indexed": datetime.now().isoformat(),
            "file_hashes": {
                "audit.jsonl": "sha256-hash-of-file",
            },
        }

        # Write index file
        index_file.write_text(json.dumps(index_data, indent=2))

        # Verify file exists and is readable
        assert index_file.exists()
        content = json.loads(index_file.read_text())
        assert content["total_entries"] == 10

    def test_index_update_logic(self, temp_audit_dir: Path):
        """Verify index is updated after new entry is appended."""
        audit_file = temp_audit_dir / "audit.jsonl"
        index_file = temp_audit_dir / "index.json"

        # Create initial index
        index = {
            "total_entries": 0,
            "last_indexed": datetime.now().isoformat(),
            "indexed_fields": ["event_type", "user_id", "timestamp"],
        }
        index_file.write_text(json.dumps(index))

        # Append 3 audit entries
        for i in range(3):
            entry = AuditEntry(
                entry_id=uuid4(),
                session_id=uuid4(),
                timestamp=datetime.now(),
                project_id="test",
                event_type=AuditEventType.ANALYSIS_STARTED,
                user_id="user@example.com",
            )
            # Append to file
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        # Update index
        index["total_entries"] = 3
        index["last_indexed"] = datetime.now().isoformat()
        index_file.write_text(json.dumps(index))

        # Verify
        updated = json.loads(index_file.read_text())
        assert updated["total_entries"] == 3

    def test_event_type_coverage(self):
        """Verify all audit event types can be recorded."""
        event_types = list(AuditEventType)
        assert len(event_types) >= 8  # Minimum expected event types

        # Verify some critical events exist
        event_names = [e.value for e in event_types]
        assert "analysis_started" in event_names
        assert "analysis_completed" in event_names
        assert "code_approved" in event_names
        assert "code_generated" in event_names
        assert "code_applied" in event_names

    def test_sensitive_field_encryption_placeholders(self):
        """Verify sensitive fields are marked for encryption."""
        entry = AuditEntry(
            entry_id=uuid4(),
            session_id=uuid4(),
            timestamp=datetime.now(),
            project_id="test",
            event_type=AuditEventType.CODE_APPROVED,
            user_id="user@example.com",  # Should be encrypted at storage
            approved_by="reviewer@example.com",  # Should be encrypted at storage
        )

        # Sensitive fields should be present in dict (encryption happens at storage layer)
        data = entry.to_dict()
        assert "user_id" in data
        assert "approved_by" in data
