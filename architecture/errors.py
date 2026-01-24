"""
Error types for the architecture module.
"""


class ArchitectureError(Exception):
    """Base error for architecture module."""

    pass


class LanguageDetectionError(ArchitectureError):
    """Could not detect language with sufficient confidence.

    Raised when:
    - No language signals are detected
    - Language detection confidence is below 90% threshold
    - Multiple conflicting signals cannot be resolved
    """

    def __init__(self, message: str, confidence: float = 0.0, signals: list = None):
        super().__init__(message)
        self.confidence = confidence
        self.signals = signals or []


class FrameworkDetectionError(ArchitectureError):
    """Could not detect framework.

    Raised when framework detection fails for a detected language.
    Note: This is a soft failure - a project may not use a framework.
    """

    def __init__(self, message: str, language: str = None):
        super().__init__(message)
        self.language = language


class LanguageMismatchError(ArchitectureError):
    """Generated code language doesn't match project.

    Raised when validate_language_match detects that generated code
    is in a different language than the project's detected language.

    This is a CRITICAL error - generating wrong-language code must NEVER happen.
    """

    def __init__(
        self,
        message: str,
        expected_language: str = None,
        detected_language: str = None,
    ):
        super().__init__(message)
        self.expected_language = expected_language
        self.detected_language = detected_language
