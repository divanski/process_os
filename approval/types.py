"""
Approval Workflow Data Model - Type Definitions

Domain entities for user approval workflow and review process.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class ApprovalStatus(Enum):
    """State of the approval workflow."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewSummary:
    """
    Review information presented in approval modal.

    Contains architecture analysis results and recommendations for user review.
    Displays patterns, conventions, confidence scores, and potential issues.
    """

    session_id: UUID
    analysis_id: UUID
    timestamp: datetime

    # Analysis results
    detected_language: str
    detected_framework: str
    overall_confidence: float  # [0.0, 1.0]

    # Recommendations
    patterns_to_use: List[Dict[str, Any]] = field(default_factory=list)
    conventions_to_apply: List[Dict[str, Any]] = field(default_factory=list)
    potential_issues: List[str] = field(default_factory=list)

    # Conflict information
    detected_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    conflict_warning: Optional[str] = None

    # Code preview
    generated_code_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": str(self.session_id),
            "analysis_id": str(self.analysis_id),
            "timestamp": self.timestamp.isoformat(),
            "detected_language": self.detected_language,
            "detected_framework": self.detected_framework,
            "overall_confidence": self.overall_confidence,
            "patterns_to_use": self.patterns_to_use,
            "conventions_to_apply": self.conventions_to_apply,
            "potential_issues": self.potential_issues,
            "detected_conflicts": self.detected_conflicts,
            "conflict_warning": self.conflict_warning,
            "generated_code_preview": self.generated_code_preview,
        }


@dataclass
class ApprovalWorkflow:
    """
    State machine for code generation approval.

    Tracks the approval state from initial request through user decision.
    - State: pending → approved/rejected (one-way transition)
    - Prevents accidental approvals (explicit user action required)
    - Records approval metadata and reasoning
    """

    workflow_id: UUID
    session_id: UUID
    analysis_id: UUID

    # State management
    status: ApprovalStatus = ApprovalStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None

    # Review information
    review_summary: Optional[ReviewSummary] = None

    # Approval decision
    reviewer_id: Optional[str] = None  # Encrypted
    approval_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    review_duration_seconds: float = 0.0

    def approve(self, reviewer_id: str, comment: Optional[str] = None) -> None:
        """Record approval decision."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve workflow in {self.status} state")
        self.status = ApprovalStatus.APPROVED
        self.reviewer_id = reviewer_id
        self.approval_comment = comment
        self.reviewed_at = datetime.now()
        self._calculate_review_duration()

    def reject(self, reviewer_id: str, reason: str) -> None:
        """Record rejection decision."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject workflow in {self.status} state")
        self.status = ApprovalStatus.REJECTED
        self.reviewer_id = reviewer_id
        self.rejection_reason = reason
        self.reviewed_at = datetime.now()
        self._calculate_review_duration()

    def _calculate_review_duration(self) -> None:
        """Calculate time spent in review."""
        if self.reviewed_at:
            delta = self.reviewed_at - self.started_at
            self.review_duration_seconds = delta.total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workflow_id": str(self.workflow_id),
            "session_id": str(self.session_id),
            "analysis_id": str(self.analysis_id),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_summary": self.review_summary.to_dict() if self.review_summary else None,
            "reviewer_id": self.reviewer_id,  # Encrypted at storage
            "approval_comment": self.approval_comment,
            "rejection_reason": self.rejection_reason,
            "review_duration_seconds": self.review_duration_seconds,
        }
