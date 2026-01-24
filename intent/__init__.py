"""
ProcessOS Intent Module

Natural language intent analysis for the Dynamic Integration Engine.
Parses user requests and identifies integration type and scope.
"""

from typing import TYPE_CHECKING, Optional

from .types import (
    Clarification,
    ClarificationOption,
    Intent,
    IntegrationScope,
    ResolvedClarification,
)
from .parser import IntentParser
from .clarifier import (
    Clarifier,
    ClarificationSession,
    ClarificationHandler,
    ConsoleClarificationHandler,
)

if TYPE_CHECKING:
    from ..discovery import ProjectContext

__all__ = [
    # Data models
    "Intent",
    "IntegrationScope",
    "Clarification",
    "ClarificationOption",
    "ResolvedClarification",
    # Parser
    "IntentParser",
    # Clarifier
    "Clarifier",
    "ClarificationSession",
    "ClarificationHandler",
    "ConsoleClarificationHandler",
    # Errors
    "IntentParseError",
    "LLMUnavailableError",
    # Convenience functions
    "parse_intent",
]


class IntentParseError(Exception):
    """Failed to parse user intent."""

    def __init__(self, message: str, raw_request: Optional[str] = None):
        self.raw_request = raw_request
        super().__init__(message)


class LLMUnavailableError(Exception):
    """Claude API is unavailable or rate-limited."""

    def __init__(self, message: str = "LLM API unavailable", retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message)


def parse_intent(request: str, project_context: Optional["ProjectContext"] = None) -> Intent:
    """
    Convenience function to parse user intent.

    Args:
        request: Natural language integration request
        project_context: Optional project context for better analysis

    Returns:
        Intent object with parsed details

    Raises:
        IntentParseError: If intent cannot be determined
        LLMUnavailableError: If LLM API is unavailable
    """
    parser = IntentParser(project_context=project_context)
    return parser.parse(request)
