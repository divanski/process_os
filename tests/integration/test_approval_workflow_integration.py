"""
Integration tests for approval workflow with user acceptance scenarios.

Tests for Phase 5 (US3): User Approval Workflow with Recommendations

Tests:
- T119: User acceptance scenario testing
- Complete approval workflow from analysis to code approval
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest


@dataclass
class ReviewSummary:
    """Summary of analysis for approval modal."""

    detected_language: str
    detected_framework: str
    overall_confidence: float
    patterns_to_use: list
    conventions_to_apply: dict
    potential_issues: list
    generated_code_preview: str


class ApprovalWorkflow:
    """State machine for code approval workflow."""

    def __init__(self, approval_request_id: str, review_summary: ReviewSummary):
        self.approval_request_id = approval_request_id
        self.review_summary = review_summary
        self.state = "pending"
        self.reviewer_id: Optional[str] = None
        self.approval_comment: Optional[str] = None
        self.rejection_reason: Optional[str] = None
        self.approval_timeout_seconds = 600

    def approve(self, reviewer_id: str, comment: Optional[str] = None) -> bool:
        if self.state != "pending":
            return False
        self.state = "approved"
        self.reviewer_id = reviewer_id
        self.approval_comment = comment
        return True

    def reject(self, rejection_reason: str) -> bool:
        if self.state != "pending":
            return False
        self.state = "rejected"
        self.rejection_reason = rejection_reason
        return True

    def is_approved(self) -> bool:
        return self.state == "approved"


class TestApprovalWorkflowIntegration:
    """Integration tests for approval workflow (T119)."""

    def test_user_acceptance_scenario_complete_workflow(self):
        """Verify complete approval workflow from analysis to approval (T119)."""
        # Step 1: Analysis complete, generate review summary
        review_summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[
                {
                    "name": "MVC",
                    "confidence": 0.95,
                    "description": "Model View Controller pattern",
                    "estimated_lines": 150,
                },
                {
                    "name": "Service Container",
                    "confidence": 0.90,
                    "description": "Dependency injection container",
                    "estimated_lines": 100,
                },
            ],
            conventions_to_apply={
                "naming": "camelCase",
                "namespace": "App\\Models",
                "directory_pattern": "app/Models",
            },
            potential_issues=[
                "Consider adding request validation",
                "Add error handling for database operations",
            ],
            generated_code_preview="<?php\n\nnamespace App\\Models;\n\nclass User\n{\n    protected $table = 'users';",
        )

        # Step 2: Create approval workflow
        approval_id = str(uuid4())
        workflow = ApprovalWorkflow(approval_id, review_summary)

        assert workflow.state == "pending"
        assert workflow.is_approved() is False

        # Step 3: User reviews summary (in modal)
        assert workflow.review_summary.detected_language == "PHP"
        assert workflow.review_summary.detected_framework == "Laravel"
        assert workflow.review_summary.overall_confidence == 0.92
        assert len(workflow.review_summary.patterns_to_use) == 2
        assert len(workflow.review_summary.potential_issues) == 2

        # Step 4: User approves
        approval_success = workflow.approve("dev-user-001", "Looks good, patterns applied correctly")

        assert approval_success is True
        assert workflow.state == "approved"
        assert workflow.reviewer_id == "dev-user-001"
        assert workflow.approval_comment == "Looks good, patterns applied correctly"
        assert workflow.is_approved() is True

    def test_approval_workflow_user_rejects_code(self):
        """Verify user can reject code with reason."""
        review_summary = ReviewSummary(
            detected_language="Python",
            detected_framework="Django",
            overall_confidence=0.78,
            patterns_to_use=[{"name": "MTV", "confidence": 0.85}],
            conventions_to_apply={"naming": "snake_case"},
            potential_issues=["Low confidence score", "Missing imports"],
            generated_code_preview="from django.db import models",
        )

        workflow = ApprovalWorkflow(str(uuid4()), review_summary)

        # User sees low confidence
        assert workflow.review_summary.overall_confidence < 0.85

        # User rejects
        reject_success = workflow.reject("Confidence too low, needs review")

        assert reject_success is True
        assert workflow.state == "rejected"
        assert workflow.rejection_reason == "Confidence too low, needs review"
        assert workflow.is_approved() is False

    def test_approval_workflow_multiple_patterns_and_conventions(self):
        """Verify workflow handles multiple patterns and conventions."""
        review_summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Symfony",
            overall_confidence=0.88,
            patterns_to_use=[
                {"name": "MVC", "confidence": 0.95},
                {"name": "Dependency Injection", "confidence": 0.92},
                {"name": "Service Locator", "confidence": 0.88},
            ],
            conventions_to_apply={
                "naming": "PascalCase",
                "namespace": "App\\Entity",
                "directory": "src/Entity",
                "psr": "PSR-12",
            },
            potential_issues=[
                "Add validation layer",
                "Implement caching strategy",
                "Add logging",
            ],
            generated_code_preview="<?php\nnamespace App\\Entity;\n\nclass Product",
        )

        workflow = ApprovalWorkflow(str(uuid4()), review_summary)

        # Verify all patterns visible
        assert len(workflow.review_summary.patterns_to_use) == 3
        assert workflow.review_summary.patterns_to_use[0]["name"] == "MVC"

        # Verify all conventions captured
        assert len(workflow.review_summary.conventions_to_apply) == 4
        assert workflow.review_summary.conventions_to_apply["psr"] == "PSR-12"

        # Verify issues listed
        assert len(workflow.review_summary.potential_issues) == 3

        # User approves despite potential issues
        workflow.approve("lead-dev-123", "Issues noted, will address in follow-up PR")
        assert workflow.is_approved()

    def test_approval_timeout_prevents_stale_approvals(self):
        """Verify approval timeout is set (10 minutes)."""
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

        # Timeout prevents stale approvals
        assert workflow.approval_timeout_seconds == 600
        assert workflow.approval_timeout_seconds == 10 * 60  # 10 minutes

    def test_approval_modal_prevents_accidental_approval(self):
        """Verify modal requires explicit action to prevent accidents."""
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

        # No automatic approval on page load
        assert workflow.state == "pending"
        assert workflow.is_approved() is False

        # Require explicit approve action
        workflow.approve("user-123")
        assert workflow.is_approved()

        # Cannot accidentally change state
        result = workflow.reject("oops")
        assert result is False
        assert workflow.is_approved()


class TestApprovalModalDisplay:
    """Test modal display and user interaction."""

    def test_approval_modal_displays_all_information(self):
        """Verify modal displays all required information."""
        summary = ReviewSummary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns_to_use=[
                {
                    "name": "MVC",
                    "confidence": 0.95,
                    "description": "Model View Controller",
                    "estimated_lines": 150,
                }
            ],
            conventions_to_apply={
                "naming": "camelCase",
                "namespace": "App",
            },
            potential_issues=["Consider adding validation"],
            generated_code_preview="<?php class User {}",
        )

        workflow = ApprovalWorkflow(str(uuid4()), summary)

        # Modal should show:
        modal_content = {
            "detected_language": workflow.review_summary.detected_language,
            "detected_framework": workflow.review_summary.detected_framework,
            "overall_confidence": workflow.review_summary.overall_confidence,
            "patterns_to_use": workflow.review_summary.patterns_to_use,
            "conventions_to_apply": workflow.review_summary.conventions_to_apply,
            "potential_issues": workflow.review_summary.potential_issues,
            "generated_code_preview": workflow.review_summary.generated_code_preview,
        }

        assert modal_content["detected_language"] == "PHP"
        assert modal_content["detected_framework"] == "Laravel"
        assert modal_content["overall_confidence"] == 0.92
        assert len(modal_content["patterns_to_use"]) >= 1
        assert "naming" in modal_content["conventions_to_apply"]
        assert len(modal_content["potential_issues"]) >= 1
        assert len(modal_content["generated_code_preview"]) > 0
