"""
Error types for the conventions module.
"""


class ConventionError(Exception):
    """Base error for conventions module."""

    pass


class InsufficientSampleError(ConventionError):
    """Not enough files to determine conventions reliably.

    Raised when the sample size for convention learning is too small
    to make reliable determinations about the project's conventions.
    """

    def __init__(
        self,
        message: str,
        samples_provided: int = 0,
        samples_required: int = 3,
        found_count: int = 0,
        required_count: int = 10,
    ):
        super().__init__(message)
        # Support both naming conventions for compatibility
        self.samples_provided = samples_provided or found_count
        self.samples_required = samples_required or required_count
        self.found_count = self.samples_provided
        self.required_count = self.samples_required


class InconsistentConventionsError(ConventionError):
    """Conventions in codebase are inconsistent.

    This is a WARNING, not a fatal error. When raised, the system
    should warn the user but continue with the dominant pattern.
    """

    def __init__(
        self,
        message: str,
        convention_type: str = None,
        dominant_pattern: str = None,
        confidence: float = 0.0,
    ):
        super().__init__(message)
        self.convention_type = convention_type
        self.dominant_pattern = dominant_pattern
        self.confidence = confidence
