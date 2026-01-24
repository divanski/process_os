"""
ProcessOS Agents Module

Dynamic agent and squad management for the Dynamic Integration Engine.
Handles agent creation, capability matching, and squad composition.
"""

from typing import TYPE_CHECKING, List

from .types import (
    Agent,
    AgentCapability,
    AgentStatus,
    CoordinationRule,
    CoordinationType,
    Squad,
    SquadMember,
    SquadStatus,
)
from .factory import AgentFactory
from .composer import SquadComposer
from .registry import AgentRegistry

if TYPE_CHECKING:
    pass

__all__ = [
    # Data models - Agent
    "Agent",
    "AgentCapability",
    "AgentStatus",
    # Data models - Squad
    "Squad",
    "SquadMember",
    "CoordinationRule",
    "CoordinationType",
    "SquadStatus",
    # Factory and Registry
    "AgentFactory",
    "AgentRegistry",
    "SquadComposer",
    # Errors
    "AgentError",
    "NoMatchingAgentError",
    "SquadCompositionError",
]


class AgentError(Exception):
    """Base error for agent operations."""


class NoMatchingAgentError(AgentError):
    """No agent matches the required capabilities."""

    def __init__(self, required_capabilities: List[str]):
        self.required_capabilities = required_capabilities
        super().__init__(
            f"No agent found matching capabilities: {required_capabilities}"
        )


class SquadCompositionError(AgentError):
    """Failed to compose a squad for the workflow."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Failed to compose squad: {reason}")
