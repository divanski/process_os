"""
ProcessOS Code Generation Error Classes

Custom exceptions for code generation operations.
"""


class CodegenError(Exception):
    """Base exception for code generation errors."""

    def __init__(self, message: str, file_type: str = None):
        """Initialize CodegenError.

        Args:
            message: Error message
            file_type: Type of file being generated
        """
        super().__init__(message)
        self.file_type = file_type


class ConventionMismatchError(CodegenError):
    """Raised when generated code violates project conventions."""

    def __init__(self, expected_pattern: str, actual_pattern: str):
        """Initialize ConventionMismatchError.

        Args:
            expected_pattern: Expected naming/style pattern
            actual_pattern: Actual pattern found in code
        """
        message = f"Convention mismatch: expected {expected_pattern}, got {actual_pattern}"
        super().__init__(message)
        self.expected_pattern = expected_pattern
        self.actual_pattern = actual_pattern


class ApplyError(CodegenError):
    """Raised when applying patchset fails."""

    def __init__(self, file_path: str, reason: str):
        """Initialize ApplyError.

        Args:
            file_path: Path to file that failed to apply
            reason: Reason for failure
        """
        message = f"Failed to apply {file_path}: {reason}"
        super().__init__(message, file_type="patchset")
        self.file_path = file_path
        self.reason = reason
