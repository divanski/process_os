"""
ProcessOS Intent Clarifier Module

Handles interactive clarification of ambiguous integration requests.
Provides structured question/answer flow for gathering missing information.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from .types import (
    Clarification,
    Intent,
    ResolvedClarification,
)


class ClarificationHandler(Protocol):
    """Protocol for clarification handlers."""

    def prompt_user(self, clarification: Clarification) -> str:
        """
        Prompt user with clarification question.

        Args:
            clarification: The clarification to present

        Returns:
            Selected option ID or 'custom'
        """
        ...

    def get_custom_value(self, clarification: Clarification) -> str:
        """
        Get custom value from user if 'custom' was selected.

        Args:
            clarification: The clarification context

        Returns:
            User-provided custom value
        """
        ...


@dataclass
class ClarificationSession:
    """Tracks state of a clarification session."""

    intent: Intent
    resolved: List[ResolvedClarification] = field(default_factory=list)
    current_index: int = 0
    is_complete: bool = False

    @property
    def current_clarification(self) -> Optional[Clarification]:
        """Get the current clarification to present."""
        pending = self.intent.pending_clarifications
        if self.current_index < len(pending):
            return pending[self.current_index]
        return None

    @property
    def progress(self) -> tuple[int, int]:
        """Get progress as (resolved, total)."""
        total = len(self.intent.clarifications_needed)
        resolved = len(self.intent.clarifications_resolved)
        return (resolved, total)


class Clarifier:
    """
    Manages the clarification workflow for ambiguous intents.

    Handles:
    - Prioritization of clarification questions
    - Interactive question/answer flow
    - Session state management
    - Validation of responses
    """

    def __init__(
        self,
        handler: Optional[ClarificationHandler] = None,
        auto_accept_defaults: bool = False,
    ):
        """
        Initialize the Clarifier.

        Args:
            handler: Optional clarification handler for prompting users
            auto_accept_defaults: If True, automatically accept default options
        """
        self.handler = handler
        self.auto_accept_defaults = auto_accept_defaults
        self._sessions: Dict[str, ClarificationSession] = {}

    def start_session(self, intent: Intent) -> ClarificationSession:
        """
        Start a new clarification session for an intent.

        Args:
            intent: Intent needing clarification

        Returns:
            ClarificationSession for tracking progress
        """
        session = ClarificationSession(intent=intent)
        session_id = f"{intent.integration_type}_{id(intent)}"
        self._sessions[session_id] = session
        return session

    def get_next_clarification(self, session: ClarificationSession) -> Optional[Clarification]:
        """
        Get the next clarification to present.

        Clarifications are returned in priority order (1=critical first).

        Args:
            session: The current session

        Returns:
            Next Clarification or None if complete
        """
        pending = session.intent.pending_clarifications

        if not pending:
            session.is_complete = True
            return None

        # Sort by priority (lower number = higher priority)
        sorted_pending = sorted(pending, key=lambda c: c.priority)
        return sorted_pending[0]

    def resolve(
        self,
        session: ClarificationSession,
        clarification_id: str,
        option_id: str,
        custom_value: Optional[str] = None,
    ) -> bool:
        """
        Resolve a clarification in the session.

        Args:
            session: The current session
            clarification_id: ID of clarification to resolve
            option_id: Selected option ID
            custom_value: Custom value if 'custom' selected

        Returns:
            True if resolution was successful
        """
        # Find the clarification
        clarification = next(
            (c for c in session.intent.clarifications_needed if c.id == clarification_id),
            None
        )

        if not clarification:
            return False

        # Validate option
        valid_options = [o.id for o in clarification.options]
        if option_id not in valid_options and option_id != "custom":
            return False

        # Record resolution
        session.intent.resolve_clarification(clarification_id, option_id, custom_value)
        session.resolved.append(session.intent.clarifications_resolved[-1])
        session.current_index += 1

        # Check if complete
        if not session.intent.pending_clarifications:
            session.is_complete = True

        return True

    def run_interactive(
        self,
        intent: Intent,
        handler: Optional[ClarificationHandler] = None,
    ) -> Intent:
        """
        Run interactive clarification workflow.

        Presents clarifications to user until all are resolved.

        Args:
            intent: Intent needing clarification
            handler: Optional handler (uses self.handler if not provided)

        Returns:
            Updated Intent with all clarifications resolved
        """
        handler = handler or self.handler
        if not handler:
            raise ValueError("No clarification handler provided")

        session = self.start_session(intent)

        while not session.is_complete:
            clarification = self.get_next_clarification(session)
            if not clarification:
                break

            # Check for auto-accept default
            if self.auto_accept_defaults and clarification.default:
                self.resolve(session, clarification.id, clarification.default)
                continue

            # Prompt user
            selected = handler.prompt_user(clarification)

            # Handle custom value
            custom_value = None
            if selected == "custom":
                custom_value = handler.get_custom_value(clarification)

            # Resolve
            self.resolve(session, clarification.id, selected, custom_value)

        return session.intent

    def format_clarification_prompt(self, clarification: Clarification) -> str:
        """
        Format a clarification for display.

        Args:
            clarification: The clarification to format

        Returns:
            Formatted prompt string
        """
        lines = [
            f"\n{clarification.question}",
            "",
        ]

        for i, option in enumerate(clarification.options, 1):
            default_marker = " (default)" if option.id == clarification.default else ""
            lines.append(f"  {i}. {option.label}{default_marker}")
            lines.append(f"     {option.description}")
            if option.implications:
                lines.append(f"     → {option.implications}")

        lines.append("")
        lines.append("Enter number or 'custom' for custom input: ")

        return "\n".join(lines)

    def validate_response(
        self,
        clarification: Clarification,
        response: str,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate user response to clarification.

        Args:
            clarification: The clarification context
            response: User's response

        Returns:
            Tuple of (is_valid, option_id, error_message)
        """
        response = response.strip().lower()

        # Check for 'custom'
        if response == "custom":
            return (True, "custom", None)

        # Check for numeric selection
        try:
            index = int(response) - 1
            if 0 <= index < len(clarification.options):
                return (True, clarification.options[index].id, None)
            return (False, None, f"Invalid selection. Choose 1-{len(clarification.options)}")
        except ValueError:
            pass

        # Check for option ID directly
        for option in clarification.options:
            if response == option.id.lower():
                return (True, option.id, None)

        return (False, None, "Invalid response. Enter a number or option ID.")


class ConsoleClarificationHandler:
    """
    Default clarification handler using console input/output.

    Suitable for CLI usage.
    """

    def __init__(self, clarifier: Optional[Clarifier] = None):
        """
        Initialize the console handler.

        Args:
            clarifier: Optional Clarifier for formatting
        """
        self.clarifier = clarifier or Clarifier()

    def prompt_user(self, clarification: Clarification) -> str:
        """Prompt user via console."""
        prompt = self.clarifier.format_clarification_prompt(clarification)
        print(prompt)

        while True:
            response = input().strip()
            is_valid, option_id, error = self.clarifier.validate_response(
                clarification, response
            )
            if is_valid:
                return option_id
            print(f"Error: {error}")

    def get_custom_value(self, clarification: Clarification) -> str:
        """Get custom value via console."""
        print(f"Enter custom value for '{clarification.question}':")
        return input().strip()
