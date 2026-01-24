"""
Error types for the patterns module.
"""


class PatternError(Exception):
    """Base error for patterns module."""

    pass


class PatternDiscoveryError(PatternError):
    """Failed to discover patterns.

    Raised when pattern discovery encounters an error during analysis.
    """

    def __init__(self, message: str, integration_type: str = None):
        super().__init__(message)
        self.integration_type = integration_type


class NoSimilarIntegrationsError(PatternError):
    """No similar integrations found to learn from.

    Raised when no existing integrations of the requested type
    can be found in the project. This triggers fallback to
    framework-standard patterns.
    """

    def __init__(self, message: str, integration_type: str = None, search_hints: list = None):
        super().__init__(message)
        self.integration_type = integration_type
        self.search_hints = search_hints or []
