"""
Architecture module for ProcessOS.

This module provides project architecture analysis and language/framework detection.
It is the mandatory validation gate before any code generation.

Public API:
- ArchitectureAnalyzer: Main analyzer for project architecture detection
- LanguageDetector: Detects programming language from multiple signals
- FrameworkDetector: Detects framework for a given language
- analyze_project: Convenience function to analyze a project
- validate_language_match: Validate that generated code matches project language

Types:
- ProjectArchitecture: Complete architecture profile of a project
- ProgrammingLanguage: Enum of supported programming languages
- FrameworkType: Enum of supported frameworks
- DetectionSignal: Individual signal contributing to detection
- ArchitectureReport: Report for user confirmation

Errors:
- ArchitectureError: Base error for architecture module
- LanguageDetectionError: Could not detect language with sufficient confidence
- FrameworkDetectionError: Could not detect framework
- LanguageMismatchError: Generated code language doesn't match project
"""

from process_os.architecture.types import (
    ProgrammingLanguage,
    FrameworkType,
    SignalType,
    ProjectType,
    DetectionSignal,
    ProjectArchitecture,
    ArchitectureReport,
)

from process_os.architecture.errors import (
    ArchitectureError,
    LanguageDetectionError,
    FrameworkDetectionError,
    LanguageMismatchError,
)

from process_os.architecture.detector import (
    LanguageDetector,
    FrameworkDetector,
    analyze_project,
    validate_language_match,
)

from process_os.architecture.analyzer import (
    ArchitectureAnalyzer,
)

from process_os.architecture.report import (
    TextReportFormatter,
    JSONReportFormatter,
)

__all__ = [
    # Types
    "ProgrammingLanguage",
    "FrameworkType",
    "SignalType",
    "ProjectType",
    "DetectionSignal",
    "ProjectArchitecture",
    "ArchitectureReport",
    # Errors
    "ArchitectureError",
    "LanguageDetectionError",
    "FrameworkDetectionError",
    "LanguageMismatchError",
    # Detectors
    "LanguageDetector",
    "FrameworkDetector",
    "ArchitectureAnalyzer",
    "analyze_project",
    "validate_language_match",
    # Formatters
    "TextReportFormatter",
    "JSONReportFormatter",
]
