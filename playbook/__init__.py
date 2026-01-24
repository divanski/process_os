"""
ProcessOS Playbook Module

Dynamic playbook generation for the Dynamic Integration Engine.
Creates step-by-step workflows with gates.
"""

from typing import TYPE_CHECKING, Optional

from .types import (
    DynamicPlaybook,
    GateStatus,
    GateType,
    PlaybookGate,
    PlaybookStatus,
    PlaybookStep,
    StepStatus,
    StepType,
)
from .builder import PlaybookBuilder
from .gates import (
    GateValidator,
    GateExecutor,
    CompletenessGate,
    SchemaValidationGate,
    UserApprovalGate,
    ConflictDetectionGate,
)

if TYPE_CHECKING:
    from ..discovery import ProjectContext
    from ..intent import Intent
    from ..requirements import Requirements

__all__ = [
    # Data models
    "DynamicPlaybook",
    "PlaybookStep",
    "PlaybookGate",
    "PlaybookStatus",
    "StepType",
    "StepStatus",
    "GateType",
    "GateStatus",
    # Builder & Gates
    "PlaybookBuilder",
    "GateValidator",
    "GateExecutor",
    "CompletenessGate",
    "SchemaValidationGate",
    "UserApprovalGate",
    "ConflictDetectionGate",
    # Errors
    "PlaybookError",
    "GateFailedError",
    # Convenience functions
    "build_playbook",
]


class PlaybookError(Exception):
    """Base error for playbook operations."""


class GateFailedError(PlaybookError):
    """A validation gate failed."""

    def __init__(self, gate_name: str, reason: str):
        self.gate_name = gate_name
        self.reason = reason
        super().__init__(f"Gate '{gate_name}' failed: {reason}")


def build_playbook(
    intent: "Intent",
    requirements: "Requirements",
    project_context: Optional["ProjectContext"] = None,
) -> DynamicPlaybook:
    """
    Convenience function to build a playbook.

    Args:
        intent: Parsed user intent
        requirements: Inferred requirements
        project_context: Optional project context

    Returns:
        DynamicPlaybook with steps and gates

    Raises:
        PlaybookError: If playbook generation fails
    """
    from .builder import PlaybookBuilder
    builder = PlaybookBuilder(project_context=project_context)
    return builder.build(intent=intent, requirements=requirements)
