"""
Patterns module for ProcessOS.

This module provides integration pattern discovery from existing code.
It analyzes existing similar integrations to extract architectural patterns.

Public API:
- PatternDiscoverer: Discovers integration patterns from existing similar integrations
- PatternExtractor: Extracts pattern details from identified integrations
- PatternMatcher: Matches user request to discovered patterns
- discover_integration_pattern: Convenience function to discover pattern for an integration

Types:
- IntegrationPattern: Architectural pattern for a type of integration
- PatternComponent: A component of an integration pattern
- ComponentRelationship: Relationship between pattern components
- RegistrationPattern: Pattern for registering new integrations
- RelationshipType: Types of relationships between components

Errors:
- PatternError: Base error for patterns module
- PatternDiscoveryError: Failed to discover patterns
- NoSimilarIntegrationsError: No similar integrations found to learn from
"""

from process_os.patterns.types import (
    RelationshipType,
    PatternComponent,
    ComponentRelationship,
    RegistrationPattern,
    IntegrationPattern,
    MethodSignature,
    ParameterInfo,
)

from process_os.patterns.errors import (
    PatternError,
    PatternDiscoveryError,
    NoSimilarIntegrationsError,
)

from process_os.patterns.extractor import PatternExtractor

from process_os.patterns.discoverer import (
    PatternDiscoverer,
    discover_integration_pattern,
)

from process_os.patterns.matcher import PatternMatcher

__all__ = [
    # Types
    "RelationshipType",
    "PatternComponent",
    "ComponentRelationship",
    "RegistrationPattern",
    "IntegrationPattern",
    "MethodSignature",
    "ParameterInfo",
    # Detectors & Matchers
    "PatternDiscoverer",
    "PatternExtractor",
    "PatternMatcher",
    "discover_integration_pattern",
    # Errors
    "PatternError",
    "PatternDiscoveryError",
    "NoSimilarIntegrationsError",
]
