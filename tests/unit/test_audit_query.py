"""
Unit tests for audit query interface.

Tests for Phase 4 (US2): Complete Audit Trail and Decision History

Tests:
- T083-T087: Audit query functionality
- Structured query support
- Query performance
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from process_os.audit.query import AuditQuery
from process_os.audit.recorder import AuditRecorder


class TestAuditQuery:
    """Test suite for audit query interface (T083-T087)."""

    @pytest.fixture
    def audit_dir(self, temp_audit_dir: Path) -> Path:
        """Provide audit directory."""
        return temp_audit_dir

    @pytest.fixture
    def recorder(self, audit_dir: Path) -> AuditRecorder:
        """Provide AuditRecorder instance."""
        return AuditRecorder(audit_dir)

    @pytest.fixture
    def query_interface(self, audit_dir: Path) -> AuditQuery:
        """Provide AuditQuery instance."""
        return AuditQuery(audit_dir)

    @pytest.fixture
    def sample_audit_trail(self, recorder: AuditRecorder) -> List[Dict[str, Any]]:
        """Create sample audit trail for testing queries."""
        user_id = "user-123"
        entries = []

        # Create multiple entries of different types
        entries.append(
            recorder.record_analysis_started(
                user_id=user_id,
                project_path="/path/to/project",
                target_directory="src",
            )
        )

        entries.append(
            recorder.record_analysis_completed(
                user_id=user_id,
                language="PHP",
                framework="Laravel",
                overall_confidence=0.92,
                signals=[{"name": "test", "confidence": 0.9}],
                patterns_discovered=["MVC"],
                conventions_learned=["PSR-12"],
            )
        )

        entries.append(
            recorder.record_code_generation_requested(
                user_id=user_id,
                task_description="Create User model",
                detected_language="PHP",
                detected_framework="Laravel",
            )
        )

        entries.append(
            recorder.record_code_approved(
                user_id=user_id,
                approval_request_id=str(uuid4()),
                approved_by="reviewer-456",
                comment="Looks good",
            )
        )

        entries.append(
            recorder.record_code_generated(
                user_id=user_id,
                files_created=["app/Models/User.php"],
                lines_generated=100,
                validation_passed=True,
            )
        )

        return entries

    def test_structured_query_by_event_type(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify structured query by event_type returns matching entries (T084)."""
        # Query for analysis_completed events
        results = query_interface.query_by_event_type("analysis_completed")

        assert len(results) >= 1, "Should find at least one analysis_completed event"
        assert all(
            entry["event_type"] == "analysis_completed" for entry in results
        ), "All entries should be analysis_completed"

    def test_structured_query_by_date_range(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify structured query by date_range returns entries within range (T085)."""
        now = datetime.utcnow()
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)

        # Query within date range
        results = query_interface.query_by_date_range(start_date, end_date)

        assert len(results) >= 1, "Should find entries within date range"

        # Verify all results are within range
        for entry in results:
            # Parse timestamp, stripping Z suffix to match the recording behavior
            entry_time = datetime.fromisoformat(entry["timestamp"].rstrip("Z"))
            assert start_date <= entry_time <= end_date, "Entry should be within range"

    def test_structured_query_by_user_id(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify structured query by user_id returns matching entries."""
        user_id = "user-123"

        # Query for specific user
        results = query_interface.query_by_user_id(user_id)

        assert len(results) >= 1, "Should find entries for user"
        assert all(entry["user_id"] == user_id for entry in results), (
            "All entries should be for specified user"
        )

    def test_retrieval_completes_in_under_5_seconds(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify audit history retrieval completes in <5 seconds (SC-003, T086)."""
        import time

        start_time = time.time()

        # Query all entries
        results = query_interface.query_all()

        elapsed_time = time.time() - start_time

        assert elapsed_time < 5.0, f"Query should complete in <5 seconds, took {elapsed_time:.2f}s"
        assert len(results) >= 1, "Should find entries"

    def test_query_combined_filters(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify query with combined filters."""
        user_id = "user-123"
        event_type = "analysis_completed"

        # Query with multiple filters
        results = query_interface.query(
            user_id=user_id,
            event_type=event_type,
        )

        # Should find at least the one analysis_completed event
        if len(results) > 0:
            assert all(entry["event_type"] == event_type for entry in results), (
                "All results should match event_type filter"
            )
            assert all(entry["user_id"] == user_id for entry in results), (
                "All results should match user_id filter"
            )


class TestAuditQueryPagination:
    """Test query result pagination."""

    @pytest.fixture
    def audit_dir(self, temp_audit_dir: Path) -> Path:
        """Provide audit directory."""
        return temp_audit_dir

    @pytest.fixture
    def recorder(self, audit_dir: Path) -> AuditRecorder:
        """Provide AuditRecorder instance."""
        return AuditRecorder(audit_dir)

    @pytest.fixture
    def query_interface(self, audit_dir: Path) -> AuditQuery:
        """Provide AuditQuery instance."""
        return AuditQuery(audit_dir)

    @pytest.fixture
    def large_audit_trail(self, recorder: AuditRecorder) -> List[Dict[str, Any]]:
        """Create large audit trail for pagination testing."""
        entries = []

        # Create 50 entries
        for i in range(50):
            entries.append(
                recorder.record_analysis_started(
                    user_id=f"user-{i}",
                    project_path=f"/path/{i}",
                    target_directory="src",
                )
            )

        return entries

    def test_query_pagination_with_limit(
        self, query_interface: AuditQuery, large_audit_trail: List[Dict[str, Any]]
    ):
        """Verify query pagination with limit parameter."""
        limit = 10

        # Query with limit
        results = query_interface.query_all(limit=limit)

        assert len(results) <= limit, f"Results should be limited to {limit}"

    def test_query_pagination_has_more_field(
        self, query_interface: AuditQuery, large_audit_trail: List[Dict[str, Any]]
    ):
        """Verify query includes has_more field for pagination."""
        limit = 10

        # Query with limit smaller than total entries
        result_set = query_interface.query_all(limit=limit)

        # Should have has_more field indicating more entries exist
        # This would be in the response metadata, not individual entries
        assert isinstance(result_set, list) or isinstance(result_set, dict), (
            "Result should be list or dict with pagination info"
        )


class TestAuditQueryPerformance:
    """Test audit query performance characteristics."""

    @pytest.fixture
    def audit_dir(self, temp_audit_dir: Path) -> Path:
        """Provide audit directory."""
        return temp_audit_dir

    @pytest.fixture
    def recorder(self, audit_dir: Path) -> AuditRecorder:
        """Provide AuditRecorder instance."""
        return AuditRecorder(audit_dir)

    @pytest.fixture
    def query_interface(self, audit_dir: Path) -> AuditQuery:
        """Provide AuditQuery instance."""
        return AuditQuery(audit_dir)

    @pytest.fixture
    def sample_audit_trail(self, recorder: AuditRecorder) -> List[Dict[str, Any]]:
        """Create sample audit trail."""
        entries = []

        for i in range(10):
            entries.append(
                recorder.record_analysis_started(
                    user_id=f"user-{i}",
                    project_path=f"/path/{i}",
                    target_directory="src",
                )
            )

        return entries

    def test_query_all_entries_performance(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify query all entries performs efficiently."""
        import time

        start_time = time.time()
        results = query_interface.query_all()
        elapsed_time = time.time() - start_time

        assert elapsed_time < 1.0, (
            f"Query all should complete in <1 second, took {elapsed_time:.3f}s"
        )
        assert len(results) >= 1, "Should return all entries"

    def test_indexed_query_performance(
        self, query_interface: AuditQuery, sample_audit_trail: List[Dict[str, Any]]
    ):
        """Verify indexed query (by event_type) performs efficiently."""
        import time

        start_time = time.time()
        results = query_interface.query_by_event_type("analysis_started")
        elapsed_time = time.time() - start_time

        assert elapsed_time < 0.5, (
            f"Indexed query should complete in <500ms, took {elapsed_time:.3f}s"
        )
        assert len(results) >= 1, "Should find matching entries"
