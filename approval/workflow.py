"""
Approval workflow state machine for code generation.

Implements:
- T122-T131: ApprovalWorkflow state machine
- State transitions: pending → approved/rejected
- Reviewer tracking and timestamping
- Approval decision persistence
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReviewSummary:
    """Summary of architecture analysis for approval modal."""

    detected_language: str
    detected_framework: str
    overall_confidence: float
    patterns_to_use: List[Dict[str, Any]]
    conventions_to_apply: Dict[str, Any]
    potential_issues: List[str]
    generated_code_preview: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "detected_language": self.detected_language,
            "detected_framework": self.detected_framework,
            "overall_confidence": self.overall_confidence,
            "patterns_to_use": self.patterns_to_use,
            "conventions_to_apply": self.conventions_to_apply,
            "potential_issues": self.potential_issues,
            "generated_code_preview": self.generated_code_preview,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewSummary":
        """Create from dictionary."""
        return cls(
            detected_language=data.get("detected_language", "Unknown"),
            detected_framework=data.get("detected_framework", "Unknown"),
            overall_confidence=data.get("overall_confidence", 0.0),
            patterns_to_use=data.get("patterns_to_use", []),
            conventions_to_apply=data.get("conventions_to_apply", {}),
            potential_issues=data.get("potential_issues", []),
            generated_code_preview=data.get("generated_code_preview", ""),
        )


class ApprovalWorkflow:
    """
    State machine for code approval workflow.

    Manages approval workflow states and transitions from analysis to code application.
    """

    # State constants (T123)
    STATE_PENDING = "pending"
    STATE_APPROVED = "approved"
    STATE_REJECTED = "rejected"

    def __init__(self, approval_request_id: str, review_summary: ReviewSummary):
        """
        Initialize approval workflow.

        Args:
            approval_request_id: Unique ID for this approval request
            review_summary: ReviewSummary from architecture analysis
        """
        self.approval_request_id = approval_request_id
        self.review_summary = review_summary

        # State management (T123)
        self.state = self.STATE_PENDING
        self.reviewer_id: Optional[str] = None
        self.review_duration_seconds: Optional[float] = None

        # Approval fields (T124, T127)
        self.approval_comment: Optional[str] = None

        # Rejection fields (T125, T128)
        self.rejection_reason: Optional[str] = None

        # Timestamps (T130)
        self.started_at = datetime.utcnow().isoformat() + "Z"
        self.reviewed_at: Optional[str] = None

        # Timeout (T117)
        self.approval_timeout_seconds = 600  # 10 minutes

    def approve(self, reviewer_id: str, comment: Optional[str] = None) -> bool:
        """
        Approve the generated code (T124).

        Args:
            reviewer_id: ID of person approving
            comment: Optional approval comment

        Returns:
            True if approved, False if already decided
        """
        if self.state != self.STATE_PENDING:
            return False

        self.state = self.STATE_APPROVED
        self.reviewer_id = reviewer_id
        self.approval_comment = comment
        self.reviewed_at = datetime.utcnow().isoformat() + "Z"

        # Calculate review duration
        if self.started_at:
            started = datetime.fromisoformat(self.started_at.rstrip("Z"))
            reviewed = datetime.fromisoformat(self.reviewed_at.rstrip("Z"))
            self.review_duration_seconds = (reviewed - started).total_seconds()

        return True

    def reject(self, rejection_reason: str) -> bool:
        """
        Reject the generated code (T125).

        Args:
            rejection_reason: Reason for rejection

        Returns:
            True if rejected, False if already decided
        """
        if self.state != self.STATE_PENDING:
            return False

        self.state = self.STATE_REJECTED
        self.rejection_reason = rejection_reason
        self.reviewed_at = datetime.utcnow().isoformat() + "Z"

        # Calculate review duration
        if self.started_at:
            started = datetime.fromisoformat(self.started_at.rstrip("Z"))
            reviewed = datetime.fromisoformat(self.reviewed_at.rstrip("Z"))
            self.review_duration_seconds = (reviewed - started).total_seconds()

        return True

    def is_approved(self) -> bool:
        """Check if workflow is approved."""
        return self.state == self.STATE_APPROVED

    def is_rejected(self) -> bool:
        """Check if workflow is rejected."""
        return self.state == self.STATE_REJECTED

    def is_pending(self) -> bool:
        """Check if workflow is pending."""
        return self.state == self.STATE_PENDING

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert workflow to dictionary for persistence (T131).

        Returns:
            Dictionary representation of workflow state
        """
        return {
            "approval_request_id": self.approval_request_id,
            "state": self.state,
            "review_summary": self.review_summary.to_dict(),
            "reviewer_id": self.reviewer_id,
            "review_duration_seconds": self.review_duration_seconds,
            "approval_comment": self.approval_comment,
            "rejection_reason": self.rejection_reason,
            "started_at": self.started_at,
            "reviewed_at": self.reviewed_at,
            "approval_timeout_seconds": self.approval_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalWorkflow":
        """
        Create workflow from dictionary (T131).

        Args:
            data: Dictionary representation of workflow

        Returns:
            ApprovalWorkflow instance
        """
        review_summary = ReviewSummary.from_dict(data.get("review_summary", {}))
        approval_request_id = data.get("approval_request_id", "")

        workflow = cls(approval_request_id, review_summary)
        workflow.state = data.get("state", "pending")
        workflow.reviewer_id = data.get("reviewer_id")
        workflow.review_duration_seconds = data.get("review_duration_seconds")
        workflow.approval_comment = data.get("approval_comment")
        workflow.rejection_reason = data.get("rejection_reason")
        workflow.started_at = data.get("started_at", workflow.started_at)
        workflow.reviewed_at = data.get("reviewed_at")
        workflow.approval_timeout_seconds = data.get("approval_timeout_seconds", 600)

        return workflow
