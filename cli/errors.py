"""
ProcessOS CLI Error Formatting

Provides user-friendly error messages with actionable remediation steps.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class ErrorCode(Enum):
    """ProcessOS error codes."""
    # Initialization errors (E001-E019)
    E001 = "E001"  # Project not initialized
    E002 = "E002"  # Already initialized
    E003 = "E003"  # Invalid project directory
    E004 = "E004"  # Config validation failed

    # Credential errors (E020-E039)
    E020 = "E020"  # API key not found
    E021 = "E021"  # Invalid API key
    E022 = "E022"  # Keychain access denied

    # Stack detection errors (E040-E059)
    E040 = "E040"  # No stack detected
    E041 = "E041"  # Multiple stacks detected (ambiguous)
    E042 = "E042"  # Unsupported stack

    # Task execution errors (E060-E079)
    E060 = "E060"  # Task not found
    E061 = "E061"  # Task blocked
    E062 = "E062"  # Task failed
    E063 = "E063"  # Task cancelled

    # Workspace errors (E080-E099)
    E080 = "E080"  # Workspace not found
    E081 = "E081"  # Workspace corrupted
    E082 = "E082"  # Workspace locked

    # Network errors (E100-E119)
    E100 = "E100"  # Network unavailable
    E101 = "E101"  # LLM service unavailable
    E102 = "E102"  # Rate limited


@dataclass
class ProcessOSError:
    """
    Structured error with remediation guidance.

    Attributes:
        code: Error code (e.g., E001)
        message: Human-readable error message
        remediation: Steps to fix the error
        details: Optional technical details
        related_help: Related help topic IDs
    """
    code: ErrorCode
    message: str
    remediation: str
    details: Optional[str] = None
    related_help: Optional[List[str]] = None


# Error registry with remediation guidance
ERROR_REGISTRY = {
    ErrorCode.E001: ProcessOSError(
        code=ErrorCode.E001,
        message="Project not initialized",
        remediation="Run 'processos init' to initialize ProcessOS in this project.",
        related_help=["init", "quickstart"],
    ),
    ErrorCode.E002: ProcessOSError(
        code=ErrorCode.E002,
        message="Project already initialized",
        remediation="Use 'processos status' to see current configuration, or remove .processos/ to reinitialize.",
        related_help=["status", "init"],
    ),
    ErrorCode.E003: ProcessOSError(
        code=ErrorCode.E003,
        message="Invalid project directory",
        remediation="Navigate to a valid project directory and try again.",
    ),
    ErrorCode.E004: ProcessOSError(
        code=ErrorCode.E004,
        message="Configuration validation failed",
        remediation="Run 'processos validate --fix' to automatically fix common issues, or manually edit .processos/config.yaml.",
        related_help=["config", "validate"],
    ),
    ErrorCode.E020: ProcessOSError(
        code=ErrorCode.E020,
        message="API key not found",
        remediation=(
            "Set your API key using one of these methods:\n"
            "  1. Environment variable: export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  2. .env file: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env\n"
            "  3. System keychain (if keyring installed)"
        ),
        related_help=["credentials", "setup"],
    ),
    ErrorCode.E021: ProcessOSError(
        code=ErrorCode.E021,
        message="Invalid API key",
        remediation="Verify your API key is correct. Get a new key from https://console.anthropic.com/",
        related_help=["credentials"],
    ),
    ErrorCode.E022: ProcessOSError(
        code=ErrorCode.E022,
        message="Keychain access denied",
        remediation="Grant ProcessOS access to the system keychain, or use environment variables instead.",
        related_help=["credentials"],
    ),
    ErrorCode.E040: ProcessOSError(
        code=ErrorCode.E040,
        message="No stack detected",
        remediation=(
            "ProcessOS couldn't detect your project's technology stack.\n"
            "Try:\n"
            "  1. Run 'processos init --stack python' to manually specify the stack\n"
            "  2. Ensure your project has standard configuration files (package.json, requirements.txt, etc.)"
        ),
        related_help=["fingerprint", "init"],
    ),
    ErrorCode.E041: ProcessOSError(
        code=ErrorCode.E041,
        message="Multiple stacks detected",
        remediation="Run 'processos init --stack <primary>' to specify which stack should be primary.",
        related_help=["fingerprint"],
    ),
    ErrorCode.E060: ProcessOSError(
        code=ErrorCode.E060,
        message="Task not found",
        remediation="Check your task command and try again. Use 'processos help tasks' for examples.",
        related_help=["cmd", "tasks"],
    ),
    ErrorCode.E061: ProcessOSError(
        code=ErrorCode.E061,
        message="Task blocked",
        remediation="This task needs additional input to proceed. Run 'processos status' to see what's required.",
        related_help=["resume", "status"],
    ),
    ErrorCode.E062: ProcessOSError(
        code=ErrorCode.E062,
        message="Task failed",
        remediation="Check the error details above. You may be able to resume with 'processos resume'.",
        related_help=["resume", "troubleshooting"],
    ),
    ErrorCode.E080: ProcessOSError(
        code=ErrorCode.E080,
        message="Workspace not found",
        remediation="The specified workspace doesn't exist. Use 'processos status' to list available workspaces.",
        related_help=["workspace", "status"],
    ),
    ErrorCode.E100: ProcessOSError(
        code=ErrorCode.E100,
        message="Network unavailable",
        remediation=(
            "ProcessOS requires network access for AI-powered tasks.\n"
            "Note: 'processos init', 'processos status', and 'processos help' work offline."
        ),
        related_help=["offline"],
    ),
    ErrorCode.E101: ProcessOSError(
        code=ErrorCode.E101,
        message="LLM service unavailable",
        remediation="The AI service is temporarily unavailable. Please try again later.",
        related_help=["troubleshooting"],
    ),
    ErrorCode.E102: ProcessOSError(
        code=ErrorCode.E102,
        message="Rate limited",
        remediation="You've hit the API rate limit. Wait a few moments and try again.",
        related_help=["troubleshooting"],
    ),
}


def get_error(code: ErrorCode) -> ProcessOSError:
    """
    Get error definition by code.

    Args:
        code: Error code

    Returns:
        ProcessOSError with remediation guidance
    """
    return ERROR_REGISTRY.get(code, ProcessOSError(
        code=code,
        message="Unknown error",
        remediation="Please report this issue at https://github.com/processos/processos/issues",
    ))


def format_error(
    error: ProcessOSError,
    details: Optional[str] = None,
    verbose: bool = False,
    show_help: bool = True
) -> str:
    """
    Format an error for display (T044: integrated with help system).

    Args:
        error: The error to format
        details: Optional additional details
        verbose: Whether to include verbose output
        show_help: Whether to show help topic suggestions

    Returns:
        Formatted error string
    """
    lines = [
        f"Error [{error.code.value}]: {error.message}",
    ]

    if details:
        lines.append("")
        lines.append(f"Details: {details}")

    lines.append("")
    lines.append("How to fix:")
    for line in error.remediation.split("\n"):
        lines.append(f"  {line}")

    # T044: Always show help suggestions when available
    if show_help and error.related_help:
        lines.append("")
        if len(error.related_help) == 1:
            lines.append(f"For more help: processos help {error.related_help[0]}")
        else:
            lines.append("Related help topics:")
            for topic in error.related_help:
                lines.append(f"  processos help {topic}")

    # Show error code help in verbose mode
    if verbose:
        lines.append("")
        lines.append(f"Error code documentation: processos help error-{error.code.value.lower()}")

    return "\n".join(lines)


def format_error_by_code(
    code: ErrorCode,
    details: Optional[str] = None,
    verbose: bool = False
) -> str:
    """
    Format an error by code for display.

    Args:
        code: Error code
        details: Optional additional details
        verbose: Whether to include verbose output

    Returns:
        Formatted error string
    """
    error = get_error(code)
    return format_error(error, details, verbose)


def get_help_topics_for_error(code: ErrorCode) -> List[str]:
    """
    Get relevant help topics for an error code (T044).

    Args:
        code: Error code

    Returns:
        List of help topic IDs
    """
    error = get_error(code)
    topics = list(error.related_help) if error.related_help else []

    # Add error-specific topic if it exists
    error_topic = f"error-{code.value.lower()}"
    if error_topic not in topics:
        topics.append(error_topic)

    return topics


def format_error_with_context(
    code: ErrorCode,
    details: Optional[str] = None,
    context: Optional[dict] = None,
    verbose: bool = False
) -> str:
    """
    Format error with context-aware help suggestions (T044).

    Args:
        code: Error code
        details: Optional additional details
        context: Optional context dict (e.g., project_root, current_command)
        verbose: Whether to include verbose output

    Returns:
        Formatted error string with contextual help
    """
    error = get_error(code)
    lines = [format_error(error, details, verbose, show_help=True)]

    # Add context-specific suggestions
    if context:
        suggestions = []

        # Suggest init if project not initialized
        if code == ErrorCode.E001 and context.get("project_root"):
            suggestions.append(f"Run: cd {context['project_root']} && processos init")

        # Suggest credential setup for API key errors
        if code in (ErrorCode.E020, ErrorCode.E021):
            suggestions.append("Set up credentials: processos interactive credentials")

        # Suggest fingerprint refresh for stack detection issues
        if code in (ErrorCode.E040, ErrorCode.E041):
            suggestions.append("Refresh detection: processos fingerprint")

        if suggestions:
            lines.append("")
            lines.append("Quick actions:")
            for s in suggestions:
                lines.append(f"  {s}")

    return "\n".join(lines)


class CLIError(Exception):
    """
    CLI error with structured error information.

    Attributes:
        error: ProcessOSError with remediation
        details: Optional additional details
        context: Optional context for help suggestions
    """

    def __init__(
        self,
        code: ErrorCode,
        details: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        self.error = get_error(code)
        self.details = details
        self.context = context
        super().__init__(self.format())

    @property
    def code(self) -> ErrorCode:
        """Get error code."""
        return self.error.code

    def format(self, verbose: bool = False) -> str:
        """Format error for display."""
        if self.context:
            return format_error_with_context(
                self.error.code, self.details, self.context, verbose
            )
        return format_error(self.error, self.details, verbose)

    def get_help_topics(self) -> List[str]:
        """Get related help topics."""
        return get_help_topics_for_error(self.error.code)
