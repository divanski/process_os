"""
Type definitions for the architecture module.

This module defines the core data structures for project architecture analysis:
- Enums for programming languages, frameworks, and signal types
- Dataclasses for detection signals, architecture profiles, and reports
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ProgrammingLanguage(Enum):
    """Supported programming languages.

    These are the languages ProcessOS can detect and generate code for.
    Detection uses multi-signal analysis for 100% accuracy on supported languages.
    """

    PHP = "php"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    JAVA = "java"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "ProgrammingLanguage":
        """Get language from file extension."""
        ext_map = {
            ".php": cls.PHP,
            ".phtml": cls.PHP,
            ".py": cls.PYTHON,
            ".pyw": cls.PYTHON,
            ".js": cls.JAVASCRIPT,
            ".mjs": cls.JAVASCRIPT,
            ".cjs": cls.JAVASCRIPT,
            ".ts": cls.TYPESCRIPT,
            ".tsx": cls.TYPESCRIPT,
            ".jsx": cls.JAVASCRIPT,
            ".rb": cls.RUBY,
            ".java": cls.JAVA,
        }
        return ext_map.get(ext.lower(), cls.UNKNOWN)


class FrameworkType(Enum):
    """Supported frameworks per language.

    Tier 1 frameworks (95% detection accuracy target):
    - Laravel (PHP)
    - Django (Python)
    - Express (JavaScript/Node.js)
    - Rails (Ruby)
    - Spring (Java)
    """

    # PHP Frameworks
    LARAVEL = "laravel"
    SYMFONY = "symfony"

    # Python Frameworks
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"

    # JavaScript/TypeScript Frameworks
    EXPRESS = "express"
    NESTJS = "nestjs"
    NEXTJS = "nextjs"

    # Ruby Frameworks
    RAILS = "rails"
    SINATRA = "sinatra"

    # Java Frameworks
    SPRING = "spring"

    # No framework detected
    NONE = "none"

    @classmethod
    def tier1_frameworks(cls) -> list["FrameworkType"]:
        """Get Tier 1 frameworks (95% accuracy target)."""
        return [cls.LARAVEL, cls.DJANGO, cls.EXPRESS, cls.RAILS, cls.SPRING]


class SignalType(Enum):
    """Types of detection signals.

    Detection uses multiple signal types for reliable language/framework identification.
    """

    CONFIG_FILE = "config_file"  # composer.json, package.json, etc.
    FILE_EXTENSION = "extension"  # .php, .py, .js distribution
    CONTENT_MARKER = "content"  # shebang, imports, namespace
    DIRECTORY_STRUCTURE = "directory"  # app/Providers/, manage.py


class ProjectType(Enum):
    """Type of project structure."""

    SINGLE = "single"  # Single language/framework project
    MONOREPO = "monorepo"  # Multiple projects in one repo
    MIXED = "mixed"  # Mixed languages (e.g., PHP backend + JS frontend)


@dataclass
class DetectionSignal:
    """Single detection signal for language/framework identification.

    Each signal contributes to the overall confidence score.
    Multiple agreeing signals increase confidence.
    """

    signal_type: SignalType
    source: str  # e.g., "composer.json", ".php files", "namespace declaration"
    detected_language: ProgrammingLanguage
    detected_framework: Optional[FrameworkType] = None
    confidence: float = 1.0  # 0.0-1.0
    evidence: str = ""  # e.g., "Found 'laravel/framework' in composer.json"

    def __post_init__(self):
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class ProjectArchitecture:
    """Complete architecture profile of a project.

    This is the core data structure that MUST be passed to code generation.
    Code generation MUST refuse to proceed if confidence < 0.9.
    """

    language: ProgrammingLanguage
    framework: Optional[FrameworkType]
    confidence: float  # 0.0-1.0, must be >= 0.9 to proceed with code generation
    root_path: Path
    detection_signals: list[DetectionSignal] = field(default_factory=list)
    project_type: ProjectType = ProjectType.SINGLE
    target_directory: Optional[Path] = None  # for monorepos

    def __post_init__(self):
        """Validate architecture data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def can_proceed_with_generation(self) -> bool:
        """Check if confidence is high enough to proceed with code generation.

        Returns True if confidence >= 0.9 (90% threshold per FR-003).
        """
        return self.confidence >= 0.9

    def get_effective_path(self) -> Path:
        """Get the effective project path (considering target_directory for monorepos)."""
        if self.target_directory:
            return self.root_path / self.target_directory
        return self.root_path


@dataclass
class ArchitectureReport:
    """Report presented to user before code generation.

    Users must review and approve this report before code generation proceeds.
    The report includes detected architecture, patterns, conventions, and any warnings.
    """

    # Import these at runtime to avoid circular imports
    architecture: "ProjectArchitecture"
    patterns: list = field(default_factory=list)  # list[IntegrationPattern]
    conventions: Optional[object] = None  # CodeConventions
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    user_approved: bool = False
    user_corrections: Optional[dict] = None
    generated_at: datetime = field(default_factory=datetime.now)

    def approve(self) -> None:
        """Mark the report as user-approved."""
        self.user_approved = True

    def add_correction(self, key: str, value: object) -> None:
        """Add a user correction to the report."""
        if self.user_corrections is None:
            self.user_corrections = {}
        self.user_corrections[key] = value

    def to_text(self) -> str:
        """Generate human-readable text report."""
        lines = [
            "=" * 60,
            "ARCHITECTURE REPORT",
            "=" * 60,
            "",
            f"Language: {self.architecture.language.value.upper()}",
            f"Framework: {self.architecture.framework.value if self.architecture.framework else 'None'}",
            f"Confidence: {self.architecture.confidence * 100:.1f}%",
            f"Project Type: {self.architecture.project_type.value}",
            "",
        ]

        if self.architecture.detection_signals:
            lines.append("Detection Signals:")
            for signal in self.architecture.detection_signals:
                lines.append(f"  - [{signal.signal_type.value}] {signal.source}: {signal.evidence}")
            lines.append("")

        if self.patterns:
            lines.append(f"Patterns Found: {len(self.patterns)}")
            for pattern in self.patterns:
                lines.append(f"  - {getattr(pattern, 'pattern_name', str(pattern))}")
            lines.append("")

        if self.recommendations:
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")
            lines.append("")

        if self.warnings:
            lines.append("⚠️ Warnings:")
            for warn in self.warnings:
                lines.append(f"  - {warn}")
            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Status: {'✅ APPROVED' if self.user_approved else '⏳ PENDING APPROVAL'}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Generate JSON-serializable dict."""
        return {
            "architecture": {
                "language": self.architecture.language.value,
                "framework": self.architecture.framework.value if self.architecture.framework else None,
                "confidence": self.architecture.confidence,
                "root_path": str(self.architecture.root_path),
                "project_type": self.architecture.project_type.value,
                "target_directory": str(self.architecture.target_directory) if self.architecture.target_directory else None,
                "detection_signals": [
                    {
                        "signal_type": s.signal_type.value,
                        "source": s.source,
                        "detected_language": s.detected_language.value,
                        "detected_framework": s.detected_framework.value if s.detected_framework else None,
                        "confidence": s.confidence,
                        "evidence": s.evidence,
                    }
                    for s in self.architecture.detection_signals
                ],
            },
            "patterns": [getattr(p, "pattern_name", str(p)) for p in self.patterns],
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "user_approved": self.user_approved,
            "user_corrections": self.user_corrections,
            "generated_at": self.generated_at.isoformat(),
        }
