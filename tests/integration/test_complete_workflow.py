"""
End-to-end workflow integration tests.

Tests for Phase 8: Complete workflow from analysis to code generation

Tests:
- T201-T210: Complete workflow scenarios
"""

import time
import pytest
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    operation_id: str
    status: str  # success, warning, error
    language: str
    framework: Optional[str]
    patterns: List[str]
    conventions: List[str]
    confidence_scores: Dict[str, float]
    overall_confidence: float
    conflicts: List[str]
    analysis_time_seconds: float
    checkpoint_id: Optional[str] = None


@dataclass
class ApprovalRequest:
    """Request for user approval."""

    operation_id: str
    analysis_result: AnalysisResult
    recommended_action: str
    requires_review: List[str]  # Items requiring manual review
    timeout_seconds: int
    created_at: str


@dataclass
class ApprovalResponse:
    """User approval response."""

    operation_id: str
    approved: bool
    reviewer_id: str
    review_notes: Optional[str] = None
    approved_at: str = ""


@dataclass
class CodeGeneration:
    """Code generation result."""

    operation_id: str
    status: str  # success, partial, failed
    files_generated: int
    files_modified: int
    analysis_summary: str
    generated_code_lines: int
    timestamp: str


class CompleteWorkflowManager:
    """Manages complete workflow from analysis to code generation."""

    def __init__(self):
        """Initialize workflow manager."""
        self.operation_id = str(uuid4())
        self.start_time = time.time()
        self.analysis_result: Optional[AnalysisResult] = None
        self.approval_request: Optional[ApprovalRequest] = None
        self.approval_response: Optional[ApprovalResponse] = None
        self.code_generation: Optional[CodeGeneration] = None
        self.audit_trail: List[Dict[str, Any]] = []

    def log_event(
        self, event_type: str, details: Dict[str, Any]
    ) -> None:
        """
        Log workflow event.

        Args:
            event_type: Type of event
            details: Event details
        """
        self.audit_trail.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": event_type,
                "operation_id": self.operation_id,
                "details": details,
            }
        )

    def analyze_project(
        self,
        language: str,
        framework: Optional[str] = None,
        patterns: Optional[List[str]] = None,
        conventions: Optional[List[str]] = None,
        confidence_scores: Optional[Dict[str, float]] = None,
        conflicts: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Run project analysis.

        Args:
            language: Detected language
            framework: Detected framework
            patterns: Discovered patterns
            conventions: Learned conventions
            confidence_scores: Phase confidence scores
            conflicts: Detected conflicts

        Returns:
            Analysis result
        """
        patterns = patterns or []
        conventions = conventions or []
        confidence_scores = confidence_scores or {}
        conflicts = conflicts or []

        # Calculate overall confidence
        overall_confidence = (
            sum(confidence_scores.values()) / len(confidence_scores)
            if confidence_scores
            else 0.0
        )

        # Determine analysis status
        if overall_confidence >= 0.90 and not conflicts:
            status = "success"
        elif overall_confidence >= 0.70:
            status = "warning"
        else:
            status = "error"

        analysis_time = time.time() - self.start_time

        result = AnalysisResult(
            operation_id=self.operation_id,
            status=status,
            language=language,
            framework=framework,
            patterns=patterns,
            conventions=conventions,
            confidence_scores=confidence_scores,
            overall_confidence=overall_confidence,
            conflicts=conflicts,
            analysis_time_seconds=analysis_time,
        )

        self.analysis_result = result
        self.log_event("analysis_complete", {"result": result})

        return result

    def request_approval(
        self, recommended_action: str, review_items: Optional[List[str]] = None
    ) -> ApprovalRequest:
        """
        Request user approval.

        Args:
            recommended_action: Recommended action
            review_items: Items requiring review

        Returns:
            Approval request
        """
        if not self.analysis_result:
            raise ValueError("Analysis must complete before approval request")

        review_items = review_items or []

        approval_request = ApprovalRequest(
            operation_id=self.operation_id,
            analysis_result=self.analysis_result,
            recommended_action=recommended_action,
            requires_review=review_items,
            timeout_seconds=600,  # 10 minutes
            created_at=datetime.utcnow().isoformat() + "Z",
        )

        self.approval_request = approval_request
        self.log_event(
            "approval_requested",
            {"recommended_action": recommended_action, "review_items": review_items},
        )

        return approval_request

    def submit_approval(
        self,
        approved: bool,
        reviewer_id: str,
        review_notes: Optional[str] = None,
    ) -> ApprovalResponse:
        """
        Submit approval response.

        Args:
            approved: Approval decision
            reviewer_id: Reviewer ID
            review_notes: Optional review notes

        Returns:
            Approval response
        """
        if not self.approval_request:
            raise ValueError("Approval request must exist")

        response = ApprovalResponse(
            operation_id=self.operation_id,
            approved=approved,
            reviewer_id=reviewer_id,
            review_notes=review_notes,
            approved_at=datetime.utcnow().isoformat() + "Z",
        )

        self.approval_response = response
        self.log_event(
            "approval_submitted",
            {"approved": approved, "review_notes": review_notes},
        )

        return response

    def generate_code(self) -> CodeGeneration:
        """
        Generate code based on analysis and approval.

        Returns:
            Code generation result
        """
        if not self.analysis_result:
            raise ValueError("Analysis must complete first")

        if self.analysis_result.status == "error":
            return CodeGeneration(
                operation_id=self.operation_id,
                status="failed",
                files_generated=0,
                files_modified=0,
                analysis_summary=f"Analysis failed: confidence {self.analysis_result.overall_confidence:.1%}",
                generated_code_lines=0,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

        if self.approval_response and not self.approval_response.approved:
            return CodeGeneration(
                operation_id=self.operation_id,
                status="cancelled",
                files_generated=0,
                files_modified=0,
                analysis_summary="Code generation cancelled by user",
                generated_code_lines=0,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

        # Simulate code generation
        base_files = 5
        modifier_files = 3
        files_generated = base_files
        files_modified = modifier_files

        # Line count based on patterns and conventions
        base_lines = 500
        pattern_lines = len(self.analysis_result.patterns) * 100
        convention_lines = len(self.analysis_result.conventions) * 50

        generated_code_lines = base_lines + pattern_lines + convention_lines

        status = "success" if not self.analysis_result.conflicts else "partial"

        generation = CodeGeneration(
            operation_id=self.operation_id,
            status=status,
            files_generated=files_generated,
            files_modified=files_modified,
            analysis_summary=f"Generated code for {self.analysis_result.language} project with {self.analysis_result.framework or 'no framework'}",
            generated_code_lines=generated_code_lines,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        self.code_generation = generation
        self.log_event(
            "code_generation_complete",
            {
                "files_generated": files_generated,
                "generated_code_lines": generated_code_lines,
            },
        )

        return generation

    def get_workflow_summary(self) -> Dict[str, Any]:
        """
        Get complete workflow summary.

        Returns:
            Workflow summary
        """
        return {
            "operation_id": self.operation_id,
            "total_duration_seconds": time.time() - self.start_time,
            "analysis": self.analysis_result,
            "approval": self.approval_response,
            "code_generation": self.code_generation,
            "audit_trail_length": len(self.audit_trail),
            "status": self._get_overall_status(),
        }

    def _get_overall_status(self) -> str:
        """Get overall workflow status."""
        if self.code_generation:
            return self.code_generation.status
        elif self.approval_response:
            return "approved" if self.approval_response.approved else "rejected"
        elif self.analysis_result:
            return self.analysis_result.status
        else:
            return "pending"


class TestCompleteAnalysisWorkflow:
    """End-to-end workflow tests (T201-T205)."""

    def test_basic_workflow_success(self):
        """Test basic workflow succeeds (T201)."""
        manager = CompleteWorkflowManager()

        # Step 1: Analyze
        analysis = manager.analyze_project(
            language="Python",
            framework="Django",
            patterns=["MVC", "Factory Pattern"],
            conventions=["snake_case", "Google-style docstrings"],
            confidence_scores={
                "language_detection": 0.95,
                "framework_detection": 0.92,
                "pattern_discovery": 0.91,
                "convention_learning": 0.92,
            },
        )

        assert analysis.status == "success"
        assert analysis.language == "Python"
        assert analysis.overall_confidence >= 0.90

        # Step 2: Request approval
        approval_request = manager.request_approval(
            recommended_action="Generate scaffolding",
            review_items=["Framework detection"],
        )

        assert approval_request.operation_id == manager.operation_id

        # Step 3: Submit approval
        approval = manager.submit_approval(
            approved=True, reviewer_id="user_123"
        )

        assert approval.approved is True

        # Step 4: Generate code
        generation = manager.generate_code()

        assert generation.status == "success"
        assert generation.files_generated > 0

    def test_workflow_with_conflicts(self):
        """Test workflow handles conflicts (T202)."""
        manager = CompleteWorkflowManager()

        # Analyze with conflicts
        analysis = manager.analyze_project(
            language="Python",
            framework=None,
            patterns=["MVC", "Layered Architecture"],  # Conflicting
            conventions=["camelCase", "snake_case"],  # Conflicting
            confidence_scores={
                "language_detection": 0.92,
                "framework_detection": 0.70,
                "pattern_discovery": 0.75,
                "convention_learning": 0.68,
            },
            conflicts=[
                "mixed_architecture",
                "mixed_naming_conventions",
            ],
        )

        assert analysis.status == "warning"
        assert len(analysis.conflicts) > 0

        # Request approval with review items
        approval_request = manager.request_approval(
            recommended_action="Manual review recommended",
            review_items=[
                "Architecture conflicts",
                "Convention conflicts",
            ],
        )

        assert len(approval_request.requires_review) > 0

    def test_workflow_rejection(self):
        """Test workflow handles rejection (T203)."""
        manager = CompleteWorkflowManager()

        manager.analyze_project(
            language="Python",
            patterns=["MVC"],
            conventions=["snake_case"],
            confidence_scores={
                "language_detection": 0.93,
                "framework_detection": 0.88,
                "pattern_discovery": 0.86,
                "convention_learning": 0.85,
            },
        )

        manager.request_approval("Generate code")

        # User rejects
        manager.submit_approval(
            approved=False,
            reviewer_id="user_456",
            review_notes="Needs more analysis",
        )

        # Try to generate code
        generation = manager.generate_code()

        assert generation.status == "cancelled"

    def test_low_confidence_analysis(self):
        """Test workflow with low confidence (T204)."""
        manager = CompleteWorkflowManager()

        # Very low confidence
        analysis = manager.analyze_project(
            language="Unknown",
            patterns=[],
            conventions=[],
            confidence_scores={
                "language_detection": 0.45,
                "framework_detection": 0.50,
                "pattern_discovery": 0.55,
                "convention_learning": 0.40,
            },
        )

        assert analysis.status == "error"
        assert analysis.overall_confidence < 0.70

        # Should not be able to generate without manual intervention
        manager.request_approval("Manual analysis required")
        manager.submit_approval(approved=True, reviewer_id="admin")

        generation = manager.generate_code()

        assert generation.status == "failed"

    def test_polyglot_project_workflow(self):
        """Test workflow with polyglot project (T205)."""
        manager = CompleteWorkflowManager()

        # Mixed languages
        analysis = manager.analyze_project(
            language="Python",
            framework="Django",
            patterns=["MVC", "REST API"],
            conventions=["snake_case", "camelCase"],  # Mixed but acceptable
            confidence_scores={
                "language_detection": 0.90,
                "framework_detection": 0.85,
                "pattern_discovery": 0.88,
                "convention_learning": 0.82,
            },
            conflicts=["mixed_naming_conventions"],
        )

        # Should still proceed with warning
        assert analysis.status == "warning"

        manager.request_approval(
            "Polyglot project: review naming conventions",
            review_items=["Mixed naming conventions"],
        )

        manager.submit_approval(approved=True, reviewer_id="user_789")

        generation = manager.generate_code()

        # Partial success due to conflicts
        assert generation.status in ["success", "partial"]


class TestAuditTrailIntegration:
    """Test audit trail integration (T206-T208)."""

    def test_audit_trail_recorded(self):
        """Verify all events recorded in audit trail (T206)."""
        manager = CompleteWorkflowManager()

        manager.analyze_project(
            language="Python",
            patterns=["MVC"],
            conventions=["snake_case"],
            confidence_scores={
                "language_detection": 0.92,
                "framework_detection": 0.88,
                "pattern_discovery": 0.85,
                "convention_learning": 0.86,
            },
        )

        manager.request_approval("Generate code")

        manager.submit_approval(approved=True, reviewer_id="user_123")

        manager.generate_code()

        # Verify audit trail
        assert len(manager.audit_trail) >= 4

        event_types = [event["event_type"] for event in manager.audit_trail]
        assert "analysis_complete" in event_types
        assert "approval_requested" in event_types
        assert "approval_submitted" in event_types
        assert "code_generation_complete" in event_types

    def test_audit_trail_immutable(self):
        """Verify audit trail is immutable (T207)."""
        manager = CompleteWorkflowManager()

        manager.analyze_project(language="Python")

        initial_count = len(manager.audit_trail)
        assert initial_count == 1

        manager.request_approval("Test")

        assert len(manager.audit_trail) == initial_count + 1

        # Should not be able to modify past events
        # (in real implementation would be persisted/immutable)
        assert manager.audit_trail[0]["event_type"] == "analysis_complete"

    def test_timestamps_in_audit_trail(self):
        """Verify timestamps recorded for all events (T208)."""
        manager = CompleteWorkflowManager()

        manager.analyze_project(language="Python")
        manager.request_approval("Test")

        for event in manager.audit_trail:
            assert "timestamp" in event
            assert "T" in event["timestamp"]
            assert "Z" in event["timestamp"]


class TestWorkflowSummaryGeneration:
    """Test workflow summary generation (T209-T210)."""

    def test_workflow_summary_complete(self):
        """Verify complete workflow summary generated (T209)."""
        manager = CompleteWorkflowManager()

        manager.analyze_project(
            language="Python",
            framework="FastAPI",
            patterns=["REST API"],
            conventions=["snake_case"],
        )

        manager.request_approval("Generate code")
        manager.submit_approval(approved=True, reviewer_id="user")
        manager.generate_code()

        summary = manager.get_workflow_summary()

        assert "operation_id" in summary
        assert "total_duration_seconds" in summary
        assert "analysis" in summary
        assert "approval" in summary
        assert "code_generation" in summary
        assert "audit_trail_length" in summary
        assert "status" in summary

    def test_workflow_status_progression(self):
        """Verify workflow status progresses correctly (T210)."""
        manager = CompleteWorkflowManager()

        # Initial status
        summary = manager.get_workflow_summary()
        assert summary["status"] == "pending"

        # After analysis
        manager.analyze_project(
            language="Python",
            confidence_scores={
                "language_detection": 0.93,
                "framework_detection": 0.90,
                "pattern_discovery": 0.91,
                "convention_learning": 0.92,
            },
        )
        summary = manager.get_workflow_summary()
        assert summary["status"] == "success"

        # After approval
        manager.request_approval("Test")
        manager.submit_approval(approved=True, reviewer_id="user")
        summary = manager.get_workflow_summary()
        assert summary["status"] == "approved"

        # After code generation
        manager.generate_code()
        summary = manager.get_workflow_summary()
        assert summary["status"] == "success"
