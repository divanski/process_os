"""
ProcessOS Discovery Module

Automatic project structure discovery for the Dynamic Integration Engine.
Detects models, routes, services, patterns, and conventions.
"""

from typing import Optional

from .context import (
    DiscoveryConfig,
    ExistingIntegration,
    LocalModel,
    ModelField,
    ProjectContext,
    ProjectConventions,
    Relationship,
    Route,
    RouteParameter,
    Service,
)

# Import analyzer and patterns for runtime use
from .analyzer import ProjectAnalyzer
from .patterns import (
    DjangoPatterns,
    ExpressPatterns,
    FrameworkPatterns,
    LaravelPatterns,
    get_patterns_for_framework,
    infer_conventions,
)

__all__ = [
    # Data models
    "ProjectContext",
    "LocalModel",
    "ModelField",
    "Relationship",
    "Route",
    "RouteParameter",
    "Service",
    "ExistingIntegration",
    "ProjectConventions",
    "DiscoveryConfig",
    # Analyzer
    "ProjectAnalyzer",
    # Patterns
    "FrameworkPatterns",
    "DjangoPatterns",
    "ExpressPatterns",
    "LaravelPatterns",
    "get_patterns_for_framework",
    "infer_conventions",
    # Errors
    "DiscoveryError",
    "ProjectTooLargeError",
    # Convenience functions
    "discover_project",
]


class DiscoveryError(Exception):
    """Base error for discovery failures."""


class ProjectTooLargeError(DiscoveryError):
    """Project exceeds file count limit."""

    def __init__(self, file_count: int, limit: int = 10000):
        self.file_count = file_count
        self.limit = limit
        super().__init__(
            f"Project has {file_count} files, exceeding limit of {limit}. "
            f"Use --target-dir <path> to narrow scope."
        )


def discover_project(project_root: str, target_dir: Optional[str] = None) -> ProjectContext:
    """
    Convenience function to discover a project.

    Args:
        project_root: Path to project root
        target_dir: Optional subdirectory to limit discovery scope

    Returns:
        ProjectContext with discovered architecture

    Raises:
        DiscoveryError: If discovery fails
        ProjectTooLargeError: If project exceeds file limit
    """
    from .analyzer import ProjectAnalyzer
    analyzer = ProjectAnalyzer(project_root, target_dir=target_dir)
    return analyzer.analyze()
