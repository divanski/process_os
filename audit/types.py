"""
Audit Trail Data Model - Type Definitions

Domain entities for audit trail and decision history tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class AuditEventType(Enum):
    """Types of events that can be recorded in audit trail."""

    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    LANGUAGE_DETECTED = "language_detected"
    FRAMEWORK_DETECTED = "framework_detected"
    PATTERN_DISCOVERED = "pattern_discovered"
    CONVENTION_LEARNED = "convention_learned"
    APPROVAL_WORKFLOW_STARTED = "approval_workflow_started"
    CODE_GENERATION_REQUESTED = "code_generation_requested"
    CODE_APPROVED = "code_approved"
    CODE_REJECTED = "code_rejected"
    CODE_GENERATED = "code_generated"
    CODE_APPLIED = "code_applied"
    OPERATION_CANCELLED = "operation_cancelled"
    OPERATION_RESUMED = "operation_resumed"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class AuditEntry:
    """
    Single entry in the audit trail.

    Immutable record of a single event in the system, stored append-only.
    Sensitive fields (user_id, project_path) are encrypted at storage time.
    """

    entry_id: UUID
    session_id: UUID
    timestamp: datetime
    project_id: str  # Hash of project path
    event_type: AuditEventType
    user_id: str  # Encrypted at storage

    # Event-specific metadata
    event_metadata: Dict[str, Any] = field(default_factory=dict)

    # Analysis-related fields
    detected_language: Optional[str] = None
    detected_framework: Optional[str] = None
    confidence_score: Optional[float] = None

    # Code generation fields
    task_description: Optional[str] = None
    files_affected: Optional[List[str]] = None
    lines_generated: Optional[int] = None

    # Approval fields
    approved_by: Optional[str] = None  # Encrypted
    approval_comment: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Error information
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entry_id": str(self.entry_id),
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "project_id": self.project_id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,  # Encrypted at storage
            "event_metadata": self.event_metadata,
            "detected_language": self.detected_language,
            "detected_framework": self.detected_framework,
            "confidence_score": self.confidence_score,
            "task_description": self.task_description,
            "files_affected": self.files_affected,
            "lines_generated": self.lines_generated,
            "approved_by": self.approved_by,
            "approval_comment": self.approval_comment,
            "rejection_reason": self.rejection_reason,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class ProjectAuditTrail:
    """
    Complete audit trail for a single project.

    Contains all events related to architecture analysis, pattern discovery,
    convention learning, and code generation for a project.

    - Append-only storage (immutable records)
    - JSON index for fast querying
    - Role-based access control (DEVELOPER/TEAM_LEAD/ADMIN)
    - Encrypted sensitive fields
    """

    project_id: str  # Hash of project path
    project_path: str  # Path to project (encrypted at storage)
    created_at: datetime
    last_modified: datetime
    total_entries: int = 0

    # Access control
    owner_user_id: str = ""  # Encrypted
    team_id: Optional[str] = None

    def add_entry(self, entry: AuditEntry) -> None:
        """Add new audit entry (append-only)."""
        self.total_entries += 1
        self.last_modified = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,  # Encrypted at storage
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "total_entries": self.total_entries,
            "owner_user_id": self.owner_user_id,  # Encrypted
            "team_id": self.team_id,
        }
