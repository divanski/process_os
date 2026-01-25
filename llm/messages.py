"""
Message type definitions for ProcessOS ↔ ClaudeCode communication protocol.

Defines all 14 message types for bi-directional WebSocket communication:
- CONNECT, READY (session establishment)
- PROGRESS (streaming updates)
- APPROVAL_REQUIRED, APPROVAL (workflow control)
- CODE_GENERATION_STARTED, CODE_GENERATED, CODE_APPLIED (code generation)
- OPERATION_CANCELLED, OPERATION_RESUMED (operation control)
- ERROR, TIMEOUT (error handling)
- AUDIT_QUERY, AUDIT_RESULTS (audit trail queries)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class Message:
    """Base class for all WebSocket messages."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConnectMessage(Message):
    """
    CONNECT message: Client initiates WebSocket session.

    Sent from ClaudeCode to ProcessOS to establish connection.
    """

    project_path: str = ""
    user_id: str = ""
    api_version: str = "1.0.0"
    client_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "CONNECT",
                "project_path": self.project_path,
                "user_id": self.user_id,
                "api_version": self.api_version,
                "client_version": self.client_version,
            }
        )
        return data


@dataclass
class ReadyMessage(Message):
    """
    READY message: Server confirms connection established.

    Sent from ProcessOS to ClaudeCode after CONNECT received.
    """

    session_id: str = ""
    project_id: str = ""
    processos_version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "READY",
                "session_id": self.session_id,
                "project_id": self.project_id,
                "processos_version": self.processos_version,
                "capabilities": self.capabilities,
            }
        )
        return data


@dataclass
class ProgressMessage(Message):
    """
    PROGRESS message: Streaming updates during analysis.

    Sent from ProcessOS to ClaudeCode every 1-2 seconds during operations.
    """

    session_id: str = ""
    phase: str = ""  # language_detection, framework_detection, pattern_discovery, convention_learning, complete
    progress_percent: float = 0.0  # 0-100
    current_step: str = ""
    step_number: int = 0
    total_steps: int = 0
    estimated_completion_seconds: float = 0.0
    is_final: bool = False

    # Confidence scores
    confidence_scores: Dict[str, float] = field(default_factory=dict)

    # Final summary (only when is_final=True)
    summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "PROGRESS",
                "session_id": self.session_id,
                "phase": self.phase,
                "progress_percent": self.progress_percent,
                "current_step": self.current_step,
                "step_number": self.step_number,
                "total_steps": self.total_steps,
                "estimated_completion_seconds": self.estimated_completion_seconds,
                "is_final": self.is_final,
                "confidence_scores": self.confidence_scores,
                "summary": self.summary,
            }
        )
        return data


@dataclass
class ApprovalRequiredMessage(Message):
    """
    APPROVAL_REQUIRED message: Request user approval before code generation.

    Sent from ProcessOS to ClaudeCode when analysis is complete.
    """

    session_id: str = ""
    analysis_id: str = ""

    # Review summary
    detected_language: str = ""
    detected_framework: str = ""
    overall_confidence: float = 0.0

    patterns_to_use: List[Dict[str, Any]] = field(default_factory=list)
    conventions_to_apply: List[Dict[str, Any]] = field(default_factory=list)
    potential_issues: List[str] = field(default_factory=list)

    # Conflict information
    detected_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    conflict_warning: Optional[str] = None

    generated_code_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "APPROVAL_REQUIRED",
                "session_id": self.session_id,
                "analysis_id": self.analysis_id,
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
        )
        return data


@dataclass
class ApprovalMessage(Message):
    """
    APPROVAL message: User approves or rejects code generation.

    Sent from ClaudeCode to ProcessOS in response to APPROVAL_REQUIRED.
    """

    session_id: str = ""
    workflow_id: str = ""
    action: str = ""  # "approve" or "reject"
    comment: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "APPROVAL",
                "session_id": self.session_id,
                "workflow_id": self.workflow_id,
                "action": self.action,
                "comment": self.comment,
                "rejection_reason": self.rejection_reason,
            }
        )
        return data


@dataclass
class CodeGenerationStartedMessage(Message):
    """CODE_GENERATION_STARTED message: Code generation has begun."""

    session_id: str = ""
    task_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "CODE_GENERATION_STARTED",
                "session_id": self.session_id,
                "task_description": self.task_description,
            }
        )
        return data


@dataclass
class CodeGeneratedMessage(Message):
    """CODE_GENERATED message: Code generation complete."""

    session_id: str = ""
    files_generated: List[str] = field(default_factory=list)
    lines_generated: int = 0
    validation_passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "CODE_GENERATED",
                "session_id": self.session_id,
                "files_generated": self.files_generated,
                "lines_generated": self.lines_generated,
                "validation_passed": self.validation_passed,
            }
        )
        return data


@dataclass
class CodeAppliedMessage(Message):
    """CODE_APPLIED message: Generated code has been applied to project."""

    session_id: str = ""
    files_written: List[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "CODE_APPLIED",
                "session_id": self.session_id,
                "files_written": self.files_written,
                "success": self.success,
            }
        )
        return data


@dataclass
class OperationCancelledMessage(Message):
    """OPERATION_CANCELLED message: User cancelled long-running operation."""

    session_id: str = ""
    operation_id: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "OPERATION_CANCELLED",
                "session_id": self.session_id,
                "operation_id": self.operation_id,
                "reason": self.reason,
            }
        )
        return data


@dataclass
class OperationResumedMessage(Message):
    """OPERATION_RESUMED message: User resumed cancelled operation."""

    session_id: str = ""
    operation_id: str = ""
    checkpoint_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "OPERATION_RESUMED",
                "session_id": self.session_id,
                "operation_id": self.operation_id,
                "checkpoint_id": self.checkpoint_id,
            }
        )
        return data


@dataclass
class ErrorMessage(Message):
    """ERROR message: Operation failed with error."""

    session_id: str = ""
    error_code: str = ""
    error_message: str = ""
    error_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "ERROR",
                "session_id": self.session_id,
                "error_code": self.error_code,
                "error_message": self.error_message,
                "error_context": self.error_context,
            }
        )
        return data


@dataclass
class TimeoutMessage(Message):
    """TIMEOUT message: Operation exceeded timeout limit."""

    session_id: str = ""
    operation_id: str = ""
    timeout_seconds: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "TIMEOUT",
                "session_id": self.session_id,
                "operation_id": self.operation_id,
                "timeout_seconds": self.timeout_seconds,
            }
        )
        return data


@dataclass
class AuditQueryMessage(Message):
    """AUDIT_QUERY message: Query audit trail."""

    session_id: str = ""
    project_id: str = ""
    query_type: str = ""  # structured or natural_language
    query: str = ""
    filters: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "AUDIT_QUERY",
                "session_id": self.session_id,
                "project_id": self.project_id,
                "query_type": self.query_type,
                "query": self.query,
                "filters": self.filters,
            }
        )
        return data


@dataclass
class AuditResultsMessage(Message):
    """AUDIT_RESULTS message: Results of audit trail query."""

    session_id: str = ""
    total_entries: int = 0
    entries: List[Dict[str, Any]] = field(default_factory=list)
    query_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "type": "AUDIT_RESULTS",
                "session_id": self.session_id,
                "total_entries": self.total_entries,
                "entries": self.entries,
                "query_time_seconds": self.query_time_seconds,
            }
        )
        return data


# Message factory for deserializing JSON to message objects
MESSAGE_TYPES = {
    "CONNECT": ConnectMessage,
    "READY": ReadyMessage,
    "PROGRESS": ProgressMessage,
    "APPROVAL_REQUIRED": ApprovalRequiredMessage,
    "APPROVAL": ApprovalMessage,
    "CODE_GENERATION_STARTED": CodeGenerationStartedMessage,
    "CODE_GENERATED": CodeGeneratedMessage,
    "CODE_APPLIED": CodeAppliedMessage,
    "OPERATION_CANCELLED": OperationCancelledMessage,
    "OPERATION_RESUMED": OperationResumedMessage,
    "ERROR": ErrorMessage,
    "TIMEOUT": TimeoutMessage,
    "AUDIT_QUERY": AuditQueryMessage,
    "AUDIT_RESULTS": AuditResultsMessage,
}


def deserialize_message(data: Dict[str, Any]) -> Message:
    """
    Deserialize JSON message data to appropriate Message object.

    Args:
        data: Dictionary containing message data with 'type' key

    Returns:
        Appropriate Message subclass instance

    Raises:
        ValueError: If message type not recognized
    """
    message_type = data.get("type")
    if message_type not in MESSAGE_TYPES:
        raise ValueError(f"Unknown message type: {message_type}")

    message_class = MESSAGE_TYPES[message_type]
    # TODO: Implement full deserialization with field mapping
    return message_class()
