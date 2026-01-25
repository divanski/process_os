"""
Integration tests for complete audit workflow.

Tests for Phase 4 (US2): Complete Audit Trail and Decision History

Tests:
- T087: End-to-end audit workflow scenario
- Recording and querying complete analysis lifecycle
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import pytest

from process_os.audit.recorder import AuditRecorder
from process_os.audit.query import AuditQuery


class TestAuditWorkflow:
    """Test complete audit workflow from analysis to code application."""

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

    def test_complete_analysis_workflow_recorded(
        self,
        recorder: AuditRecorder,
        query_interface: AuditQuery,
    ):
        """Verify complete analysis lifecycle is recorded and queryable (T087)."""
        user_id = "user-123"
        project_path = "/path/to/project"
        approval_request_id = str(uuid4())

        # Step 1: Record analysis_started
        analysis_started = recorder.record_analysis_started(
            user_id=user_id,
            project_path=project_path,
            target_directory="src",
        )
        assert analysis_started["event_type"] == "analysis_started"

        # Step 2: Record analysis_completed
        analysis_completed = recorder.record_analysis_completed(
            user_id=user_id,
            language="PHP",
            framework="Laravel",
            overall_confidence=0.92,
            signals=[
                {"name": "laravel_config", "confidence": 0.95},
                {"name": "blade_templates", "confidence": 0.90},
            ],
            patterns_discovered=["MVC", "Service Container"],
            conventions_learned=["PSR-12", "Naming Convention"],
        )
        assert analysis_completed["event_type"] == "analysis_completed"

        # Step 3: Record code_generation_requested
        code_gen_requested = recorder.record_code_generation_requested(
            user_id=user_id,
            task_description="Create User model with validation",
            detected_language="PHP",
            detected_framework="Laravel",
        )
        assert code_gen_requested["event_type"] == "code_generation_requested"

        # Step 4: Record approval_workflow_started
        approval_started = recorder.record_approval_workflow_started(
            user_id=user_id,
            approval_request_id=approval_request_id,
            patterns_to_use=["MVC", "Service Container"],
            conventions_to_apply={"naming": "camelCase", "namespace": "App"},
            recommendations=["Use validation rules", "Add error handling"],
        )
        assert approval_started["event_type"] == "approval_workflow_started"

        # Step 5: Record code_approved
        code_approved = recorder.record_code_approved(
            user_id=user_id,
            approval_request_id=approval_request_id,
            approved_by="reviewer-456",
            comment="Looks good, all patterns applied correctly",
        )
        assert code_approved["event_type"] == "code_approved"

        # Step 6: Record code_generated
        code_generated = recorder.record_code_generated(
            user_id=user_id,
            files_created=[
                "app/Models/User.php",
                "database/migrations/create_users_table.php",
                "app/Http/Requests/UserRequest.php",
            ],
            lines_generated=450,
            validation_passed=True,
        )
        assert code_generated["event_type"] == "code_generated"

        # Step 7: Record code_applied
        code_applied = recorder.record_code_applied(
            user_id=user_id,
            files_written=[
                "app/Models/User.php",
                "database/migrations/create_users_table.php",
                "app/Http/Requests/UserRequest.php",
            ],
            success=True,
        )
        assert code_applied["event_type"] == "code_applied"

        # Verify all entries can be queried
        all_entries = query_interface.query_all()
        assert len(all_entries) >= 7, "Should have at least 7 entries"

        # Verify we can query by user
        user_entries = query_interface.query_by_user_id(user_id)
        assert len(user_entries) >= 7, "Should find all entries for user"
        assert all(e["user_id"] == user_id for e in user_entries), (
            "All entries should belong to user"
        )

        # Verify we can query by event type
        analysis_events = query_interface.query_by_event_type("analysis_completed")
        assert len(analysis_events) >= 1, "Should find analysis_completed event"

        approval_events = query_interface.query_by_event_type("code_approved")
        assert len(approval_events) >= 1, "Should find code_approved event"

    def test_audit_trail_completeness(
        self,
        recorder: AuditRecorder,
        query_interface: AuditQuery,
    ):
        """Verify audit trail captures complete information about analysis."""
        user_id = "dev-001"

        # Record complete analysis
        recorder.record_analysis_started(user_id, "/project", "src")
        recorder.record_analysis_completed(
            user_id=user_id,
            language="Python",
            framework="Django",
            overall_confidence=0.88,
            signals=[{"name": "django_settings", "confidence": 0.95}],
            patterns_discovered=["MTV"],
            conventions_learned=["PEP 8"],
        )

        # Query and verify metadata completeness
        analysis_entries = query_interface.query_by_event_type("analysis_completed")
        assert len(analysis_entries) >= 1

        entry = analysis_entries[0]
        metadata = entry["metadata"]

        # Verify all expected metadata fields
        assert metadata["language"] == "Python"
        assert metadata["framework"] == "Django"
        assert metadata["overall_confidence"] == 0.88
        assert "signals" in metadata
        assert "patterns_discovered" in metadata
        assert "conventions_learned" in metadata
        assert len(metadata["patterns_discovered"]) == 1
        assert metadata["patterns_discovered"][0] == "MTV"

    def test_audit_trail_preserves_decisions(
        self,
        recorder: AuditRecorder,
        query_interface: AuditQuery,
    ):
        """Verify audit trail records decision points in workflow."""
        user_id = "team-lead-001"
        approval_id = str(uuid4())

        # Simulate approval decision
        recorder.record_approval_workflow_started(
            user_id=user_id,
            approval_request_id=approval_id,
            patterns_to_use=["ModelViewController", "Dependency Injection"],
            conventions_to_apply={"naming": "snake_case", "spacing": "4 spaces"},
            recommendations=[
                "Apply singleton for database connection",
                "Use dependency injection for services",
            ],
        )

        recorder.record_code_approved(
            user_id=user_id,
            approval_request_id=approval_id,
            approved_by="architect-001",
            comment="All recommendations addressed correctly",
        )

        # Query approval decisions
        approval_entries = query_interface.query_by_event_type("approval_workflow_started")
        assert len(approval_entries) >= 1

        entry = approval_entries[0]
        metadata = entry["metadata"]

        # Verify decision is preserved
        assert metadata["approval_request_id"] == approval_id
        assert len(metadata["patterns_to_use"]) == 2
        assert len(metadata["recommendations"]) == 2
        assert metadata["conventions_to_apply"]["naming"] == "snake_case"

        # Verify approval decision is recorded
        approval_decisions = query_interface.query_by_event_type("code_approved")
        assert len(approval_decisions) >= 1

        decision = approval_decisions[0]
        assert decision["metadata"]["approved_by"] == "architect-001"
        assert "comment" in decision["metadata"]

    def test_audit_trail_queryable_by_multiple_criteria(
        self,
        recorder: AuditRecorder,
        query_interface: AuditQuery,
    ):
        """Verify audit trail can be queried by multiple combined criteria."""
        user_id = "user-001"

        # Record several entries
        recorder.record_analysis_started(user_id, "/proj1", "src")
        recorder.record_analysis_completed(
            user_id, "PHP", "Laravel", 0.9, [], [], []
        )
        recorder.record_code_generation_requested(
            user_id, "task1", "PHP", "Laravel"
        )

        # Query by multiple criteria
        results = query_interface.query(
            user_id=user_id,
            event_type="code_generation_requested",
        )

        assert len(results) >= 1
        assert all(r["user_id"] == user_id for r in results)
        assert all(r["event_type"] == "code_generation_requested" for r in results)

    def test_audit_trail_retrievable_in_reasonable_time(
        self,
        recorder: AuditRecorder,
        query_interface: AuditQuery,
    ):
        """Verify audit trail retrieval meets performance requirement (SC-003)."""
        import time

        # Create multiple entries
        for i in range(20):
            recorder.record_analysis_started(f"user-{i}", f"/proj-{i}", "src")

        # Measure query time
        start_time = time.time()
        results = query_interface.query_all()
        elapsed_time = time.time() - start_time

        # Should complete in <5 seconds (SC-003)
        assert elapsed_time < 5.0, (
            f"Query should complete in <5 seconds, took {elapsed_time:.2f}s"
        )
        assert len(results) >= 20, "Should retrieve all entries"
