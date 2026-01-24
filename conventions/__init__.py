"""
Conventions module for ProcessOS.

This module provides code convention learning and application.
It analyzes existing codebase to learn conventions and applies them to generated code.

Public API:
- ConventionLearner: Learns coding conventions from existing codebase
- NamingAnalyzer: Analyzes naming conventions in code
- StructureAnalyzer: Analyzes directory and namespace structure
- ConventionApplier: Applies learned conventions to generated code
- learn_conventions: Convenience function to learn project conventions
- apply_conventions: Apply conventions to a code string

Types:
- CodeConventions: Coding conventions learned from the project
- NamingStyle: Naming style conventions (PascalCase, camelCase, snake_case, etc.)
- DocStyle: Documentation style (PHPDoc, JSDoc, docstring, etc.)
- ImportOrdering: Import statement ordering (grouped, alphabetical, length)
- Indentation: Indentation style (spaces_2, spaces_4, tabs)

Errors:
- ConventionError: Base error for conventions module
- InsufficientSampleError: Not enough files to determine conventions reliably
- InconsistentConventionsError: Conventions in codebase are inconsistent
"""

from process_os.conventions.types import (
    NamingStyle,
    DocStyle,
    ImportOrdering,
    Indentation,
    CodeConventions,
)

from process_os.conventions.errors import (
    ConventionError,
    InsufficientSampleError,
    InconsistentConventionsError,
)

from process_os.conventions.naming import NamingAnalyzer

from process_os.conventions.structure import StructureAnalyzer

from process_os.conventions.learner import ConventionLearner, ConventionApplier

__all__ = [
    # Types
    "NamingStyle",
    "DocStyle",
    "ImportOrdering",
    "Indentation",
    "CodeConventions",
    # Analyzers & Learners
    "NamingAnalyzer",
    "StructureAnalyzer",
    "ConventionLearner",
    "ConventionApplier",
    # Errors
    "ConventionError",
    "InsufficientSampleError",
    "InconsistentConventionsError",
]
