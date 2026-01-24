"""
ProcessOS Requirements Module

Dynamic requirements inference for the Dynamic Integration Engine.
Determines required materials and decisions for integrations.
"""

from typing import TYPE_CHECKING

from .materials import (
    APIDocumentation,
    APIEndpoint,
    APIExample,
    APIParameter,
    APISchema,
    CredentialReference,
    MaterialCollection,
)
from .types import (
    DecisionOption,
    DecisionRequirement,
    DecisionType,
    MaterialRequirement,
    MaterialType,
    Requirements,
)
from .engine import RequirementsEngine
from .collector import MaterialCollector

if TYPE_CHECKING:
    from ..intent import Intent

__all__ = [
    # Data models - Requirements
    "Requirements",
    "MaterialRequirement",
    "MaterialType",
    "DecisionRequirement",
    "DecisionType",
    "DecisionOption",
    # Data models - Materials
    "MaterialCollection",
    "APIDocumentation",
    "APIEndpoint",
    "APIParameter",
    "APISchema",
    "APIExample",
    "CredentialReference",
    # Engine & Collector
    "RequirementsEngine",
    "MaterialCollector",
    # Errors
    "RequirementsError",
    "MissingMaterialError",
    # Convenience functions
    "infer_requirements",
]


class RequirementsError(Exception):
    """Base error for requirements operations."""


class MissingMaterialError(RequirementsError):
    """Required material is missing."""

    def __init__(self, material_name: str, material_type: str):
        self.material_name = material_name
        self.material_type = material_type
        super().__init__(f"Missing required {material_type}: {material_name}")


def infer_requirements(intent: "Intent") -> Requirements:
    """
    Convenience function to infer requirements from intent.

    Args:
        intent: Parsed user intent

    Returns:
        Requirements object with materials and decisions needed

    Raises:
        RequirementsError: If inference fails
    """
    engine = RequirementsEngine()
    return engine.infer(intent)
