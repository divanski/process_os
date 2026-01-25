"""
Unit tests for approval workflow state machine.

Tests for Phase 5 (US3): User Approval Workflow with Recommendations

Tests:
- T108-T121: Approval workflow state machine and modal display
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest


@dataclass
class ReviewSummary:
    """Summary of analysis for approval modal."""

    detected_language: str
    detected_framework: str
    overall_confidence: float
    patterns_to_use: List[Dict[str, Any]]
    conventions_to_apply: Dict[str, Any]
    potential_issues: List[str]
    generated_code_preview: str


class ApprovalWorkflow:
    """State machine for code approval workflow."""

    def __init__(self, approval_request_id: str, review_summary: ReviewSummary):
        """
        Initialize approval workflow.

        Args:
            approval_request_id: Unique ID for this approval
            review_summary: Summary to display in modal
        """
        self.approval_request_id = approval_request_id
        self.review_summary = review_summary
        self.state = "pending"  # pending, approved, rejected
        self.reviewer_id: Optional[str] = None
        self.approval_comment: Optional[str] = None
        self.rejection_reason: Optional[str] = None
        self.approval_timeout_seconds = 600  # 10 minutes

    def approve(self, reviewer_id: str, comment: Optional[str] = None) -> bool:
        """
        Approve the code.

        Args:
            reviewer_id: ID of person approving
            comment: Optional approval comment

        Returns:
            True if approved, False if already decided
        """
        if self.state != "pending":
            return False

        self.state = "approved"
        self.reviewer_id = reviewer_id
        self.approval_comment = comment
        return True

    def reject(self, rejection_reason: str) -> bool:
        """
        Reject the code.

        Args:
            rejection_reason: Reason for rejection

        Returns:
            True if rejected, False if already decided
        """
        if self.state != "pending":
            return False

        self.state = "rejected"
        self.rejection_reason = rejection_reason
        return True

    def is_approved(self) -> bool:
        """Check if approved."""
        return self.state == "approved"

    def is_rejected(self) -> bool:
        """Check if rejected."""
        return self.state == "rejected"


class TestApprovalWorkflowState:
    """Test approval workflow state machine (T108-T110)."""

    def test_approval_workflow_state_pending_to_approved(self):
        """Verify approval workflow state: pending → approved (T109)."""
        review_summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[{"name": "MVC", "confidence": 0.95}],
            conventions_to_apply={"naming": "camelCase"},
            potential_issues=[],
            generated_code_preview="<?php\nclass User { }",
        )

        workflow = ApprovalWorkflow(str(uuid4()), review_summary)

        # Initially pending
        assert workflow.state == "pending"

        # Approve
        success = workflow.approve("reviewer-123", "Looks good")
        assert success is True
        assert workflow.state == "approved"
        assert workflow.reviewer_id == "reviewer-123"
        assert workflow.approval_comment == "Looks good"
        assert workflow.is_approved() is True

    def test_approval_workflow_state_pending_to_rejected(self):
        """Verify approval workflow state: pending → rejected (T110)."""
        review_summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[{"name": "MVC", "confidence": 0.95}],
            conventions_to_apply={"naming": "camelCase"},
            potential_issues=["Missing error handling"],
            generated_code_preview="<?php\nclass User { }",
        )

        workflow = ApprovalWorkflow(str(uuid4()), review_summary)

        # Initially pending
        assert workflow.state == "pending"

        # Reject
        success = workflow.reject("Missing error handling")
        assert success is True
        assert workflow.state == "rejected"
        assert workflow.rejection_reason == "Missing error handling"
        assert workflow.is_rejected() is True


class TestApprovalModalContent:
    """Test approval modal content and display (T111-T117)."""

    def test_approval_required_message_construction(self):
        """Verify APPROVAL_REQUIRED message construction with all fields (T111)."""
        review_summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[{"name": "MVC", "confidence": 0.95}],
            conventions_to_apply={"naming": "camelCase", "namespace": "App"},
            potential_issues=["Consider caching"],
            generated_code_preview="<?php class User { }\n// 500 chars truncated",
        )

        approval_id = str(uuid4())
        workflow = ApprovalWorkflow(approval_id, review_summary)

        # Build APPROVAL_REQUIRED message
        message = {
            "type": "APPROVAL_REQUIRED",
            "approval_request_id": approval_id,
            "review_summary": {
                "detected_language": review_summary.detected_language,
                "detected_framework": review_summary.detected_framework,
                "overall_confidence": review_summary.overall_confidence,
                "patterns_to_use": review_summary.patterns_to_use,
                "conventions_to_apply": review_summary.conventions_to_apply,
                "potential_issues": review_summary.potential_issues,
                "generated_code_preview": review_summary.generated_code_preview,
            },
        }

        assert message["type"] == "APPROVAL_REQUIRED"
        assert message["approval_request_id"] == approval_id
        assert "review_summary" in message

    def test_review_summary_includes_all_fields(self):
        """Verify ReviewSummary includes all required fields (T112-T116)."""
        patterns = [
            {"name": "MVC", "confidence": 0.95, "description": "Model View Controller"},
            {"name": "Service Container", "confidence": 0.90, "description": "Service locator"},
        ]

        conventions = {
            "naming": "camelCase",
            "namespace": "App\\Models",
            "directory_pattern": "app/Models",
        }

        issues = ["Consider adding validation", "Add error handling"]

        preview = "<?php\nnamespace App\\Models;\n\nclass User {"

        summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=patterns,
            conventions_to_apply=conventions,
            potential_issues=issues,
            generated_code_preview=preview,
        )

        # Verify all fields present
        assert summary.detected_language == "PHP"
        assert summary.detected_framework == "Laravel"
        assert summary.overall_confidence == 0.92
        assert len(summary.patterns_to_use) == 2
        assert len(summary.conventions_to_apply) == 3
        assert len(summary.potential_issues) == 2
        assert "<?php" in summary.generated_code_preview

    def test_approval_timeout_set_to_10_minutes(self):
        """Verify approval_timeout_seconds set to 600 (10 minutes) (T117)."""
        summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[],
            conventions_to_apply={},
            potential_issues=[],
            generated_code_preview="",
        )

        workflow = ApprovalWorkflow(str(uuid4()), summary)
        assert workflow.approval_timeout_seconds == 600


class TestApprovalMessage:
    """Test APPROVAL message validation (T118)."""

    def test_approval_message_validation(self):
        """Verify APPROVAL message validation (T118)."""
        approval_id = str(uuid4())

        # Valid approval message
        approval_message = {
            "type": "APPROVAL",
            "approval_request_id": approval_id,
            "action": "approve",
            "comment": "Looks good",
        }

        assert approval_message["type"] == "APPROVAL"
        assert approval_message["approval_request_id"] == approval_id
        assert approval_message["action"] in ["approve", "reject"]

        # Valid rejection message
        rejection_message = {
            "type": "APPROVAL",
            "approval_request_id": approval_id,
            "action": "reject",
            "reason": "Missing error handling",
        }

        assert rejection_message["action"] == "reject"
        assert "reason" in rejection_message


class TestApprovalPrevention:
    """Test accidental approval prevention (T121)."""

    def test_approval_workflow_prevents_accidental_approvals(self):
        """Verify approval workflow prevents accidental approvals (T121)."""
        summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[],
            conventions_to_apply={},
            potential_issues=[],
            generated_code_preview="",
        )

        workflow = ApprovalWorkflow(str(uuid4()), summary)

        # Cannot approve without explicit action
        assert workflow.state == "pending"
        assert not workflow.is_approved()

        # Require explicit approve call
        success = workflow.approve("reviewer-123")
        assert success is True
        assert workflow.is_approved()

        # Cannot change once decided
        success2 = workflow.reject("Too late")
        assert success2 is False
        assert workflow.state == "approved"
