"""
Type definitions for the conventions module.

This module defines data structures for code convention learning:
- Enums for naming styles, documentation styles, etc.
- Dataclass for learned code conventions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NamingStyle(Enum):
    """Naming style conventions.

    Used to classify and apply naming conventions for different identifier types.
    """

    PASCAL_CASE = "PascalCase"  # MyClassName
    CAMEL_CASE = "camelCase"  # myMethodName
    SNAKE_CASE = "snake_case"  # my_variable_name
    KEBAB_CASE = "kebab-case"  # my-file-name
    SCREAMING_SNAKE = "SCREAMING_SNAKE_CASE"  # MY_CONSTANT
    UNKNOWN = "unknown"

    @classmethod
    def detect(cls, identifier: str) -> "NamingStyle":
        """Detect the naming style of an identifier."""
        if not identifier:
            return cls.UNKNOWN

        # Check for kebab-case
        if "-" in identifier and identifier == identifier.lower():
            return cls.KEBAB_CASE

        # Check for SCREAMING_SNAKE_CASE
        if "_" in identifier and identifier == identifier.upper():
            return cls.SCREAMING_SNAKE

        # Check for snake_case
        if "_" in identifier and identifier == identifier.lower():
            return cls.SNAKE_CASE

        # Check for PascalCase (starts with uppercase, no underscores or dashes)
        if identifier[0].isupper() and "_" not in identifier and "-" not in identifier:
            return cls.PASCAL_CASE

        # Check for camelCase (starts with lowercase, has uppercase, no underscores)
        if identifier[0].islower() and any(c.isupper() for c in identifier) and "_" not in identifier:
            return cls.CAMEL_CASE

        return cls.UNKNOWN

    def convert(self, identifier: str) -> str:
        """Convert an identifier to this naming style."""
        # First, normalize to words
        words = self._to_words(identifier)
        if not words:
            return identifier

        if self == NamingStyle.PASCAL_CASE:
            return "".join(w.capitalize() for w in words)
        elif self == NamingStyle.CAMEL_CASE:
            return words[0].lower() + "".join(w.capitalize() for w in words[1:])
        elif self == NamingStyle.SNAKE_CASE:
            return "_".join(w.lower() for w in words)
        elif self == NamingStyle.KEBAB_CASE:
            return "-".join(w.lower() for w in words)
        elif self == NamingStyle.SCREAMING_SNAKE:
            return "_".join(w.upper() for w in words)
        else:
            return identifier

    @staticmethod
    def _to_words(identifier: str) -> list[str]:
        """Split an identifier into words."""
        # Handle snake_case and kebab-case
        if "_" in identifier:
            return [w for w in identifier.split("_") if w]
        if "-" in identifier:
            return [w for w in identifier.split("-") if w]

        # Handle PascalCase and camelCase
        words = []
        current_word = []
        for char in identifier:
            if char.isupper() and current_word:
                words.append("".join(current_word))
                current_word = [char]
            else:
                current_word.append(char)
        if current_word:
            words.append("".join(current_word))
        return words


class DocStyle(Enum):
    """Documentation style conventions."""

    PHPDOC = "phpdoc"  # /** @param ... */
    JSDOC = "jsdoc"  # /** @param {type} ... */
    DOCSTRING = "docstring"  # Python """..."""
    GOOGLE_DOCSTRING = "google_docstring"  # Google-style Python docstring
    NUMPY_DOCSTRING = "numpy_docstring"  # NumPy-style Python docstring
    JAVADOC = "javadoc"  # Java /** @param ... */
    NONE = "none"


class ImportOrdering(Enum):
    """Import statement ordering conventions."""

    GROUPED = "grouped"  # stdlib, third-party, local
    ALPHABETICAL = "alphabetical"  # A-Z ordering
    LENGTH = "length"  # Short to long
    UNKNOWN = "unknown"


class Indentation(Enum):
    """Indentation style conventions."""

    SPACES_2 = "spaces_2"
    SPACES_4 = "spaces_4"
    TABS = "tabs"
    UNKNOWN = "unknown"


@dataclass
class CodeConventions:
    """Coding conventions learned from the project.

    Conventions are only applied when confidence >= 0.7 (70% threshold).
    """

    # Naming conventions
    class_naming: NamingStyle = NamingStyle.PASCAL_CASE
    method_naming: NamingStyle = NamingStyle.CAMEL_CASE
    variable_naming: NamingStyle = NamingStyle.SNAKE_CASE
    file_naming: NamingStyle = NamingStyle.PASCAL_CASE

    # Structure conventions
    namespace_pattern: Optional[str] = None  # e.g., "App\\Services\\{Domain}\\{Type}"
    directory_pattern: str = ""  # e.g., "app/Services/{domain}/{type}/"

    # Documentation
    documentation_style: DocStyle = DocStyle.NONE

    # Formatting
    import_ordering: ImportOrdering = ImportOrdering.GROUPED
    indentation: Indentation = Indentation.SPACES_4
    line_ending: str = "\n"
    max_line_length: int = 120

    # Confidence (must be >= 0.7 to apply conventions)
    confidence: float = 1.0

    # Per-convention confidence scores (for detailed analysis)
    confidence_scores: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate conventions data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def can_apply(self) -> bool:
        """Check if confidence is high enough to apply conventions.

        Returns True if confidence >= 0.7 (70% threshold per research.md).
        """
        return self.confidence >= 0.7

    def get_naming_style(self, identifier_type: str) -> NamingStyle:
        """Get the naming style for a specific identifier type."""
        styles = {
            "class": self.class_naming,
            "method": self.method_naming,
            "function": self.method_naming,
            "variable": self.variable_naming,
            "file": self.file_naming,
            "constant": NamingStyle.SCREAMING_SNAKE,
        }
        return styles.get(identifier_type, NamingStyle.UNKNOWN)

    def apply_naming(self, identifier: str, identifier_type: str) -> str:
        """Apply naming convention to an identifier."""
        style = self.get_naming_style(identifier_type)
        if style == NamingStyle.UNKNOWN:
            return identifier
        return style.convert(identifier)

    def generate_namespace(self, domain: str, component_type: str) -> str:
        """Generate namespace based on pattern."""
        if not self.namespace_pattern:
            return ""
        return (
            self.namespace_pattern.replace("{Domain}", domain)
            .replace("{domain}", domain.lower())
            .replace("{Type}", component_type)
            .replace("{type}", component_type.lower())
        )

    def generate_directory(self, domain: str, component_type: str) -> str:
        """Generate directory path based on pattern."""
        if not self.directory_pattern:
            return ""
        return (
            self.directory_pattern.replace("{Domain}", domain)
            .replace("{domain}", domain.lower())
            .replace("{Type}", component_type)
            .replace("{type}", component_type.lower())
        )

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "class_naming": self.class_naming.value,
            "method_naming": self.method_naming.value,
            "variable_naming": self.variable_naming.value,
            "file_naming": self.file_naming.value,
            "namespace_pattern": self.namespace_pattern,
            "directory_pattern": self.directory_pattern,
            "documentation_style": self.documentation_style.value,
            "import_ordering": self.import_ordering.value,
            "indentation": self.indentation.value,
            "line_ending": repr(self.line_ending),
            "max_line_length": self.max_line_length,
            "confidence": self.confidence,
            "confidence_scores": self.confidence_scores,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodeConventions":
        """Create CodeConventions from a dict."""
        return cls(
            class_naming=NamingStyle(data.get("class_naming", "PascalCase")),
            method_naming=NamingStyle(data.get("method_naming", "camelCase")),
            variable_naming=NamingStyle(data.get("variable_naming", "snake_case")),
            file_naming=NamingStyle(data.get("file_naming", "PascalCase")),
            namespace_pattern=data.get("namespace_pattern"),
            directory_pattern=data.get("directory_pattern", ""),
            documentation_style=DocStyle(data.get("documentation_style", "none")),
            import_ordering=ImportOrdering(data.get("import_ordering", "grouped")),
            indentation=Indentation(data.get("indentation", "spaces_4")),
            line_ending=data.get("line_ending", "\n"),
            max_line_length=data.get("max_line_length", 120),
            confidence=data.get("confidence", 1.0),
            confidence_scores=data.get("confidence_scores", {}),
        )
