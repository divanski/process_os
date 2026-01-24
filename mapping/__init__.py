"""
ProcessOS Mapping Module

Schema mapping for the Dynamic Integration Engine.
Maps external API schemas to local models.
"""

from typing import TYPE_CHECKING, Dict, List, Optional

from .types import (
    FieldMapping,
    SchemaMapping,
    Transformation,
    UnmappedField,
)
from .mapper import SchemaMapper
from .inference import SemanticMatcher, TypeTransformer
from .interactive import InteractiveMapper, ConsoleMappingHandler, MappingHandler

if TYPE_CHECKING:
    from ..discovery import LocalModel, ProjectContext

__all__ = [
    # Data models
    "SchemaMapping",
    "FieldMapping",
    "Transformation",
    "UnmappedField",
    # Mapper
    "SchemaMapper",
    # Inference
    "SemanticMatcher",
    "TypeTransformer",
    # Interactive
    "InteractiveMapper",
    "ConsoleMappingHandler",
    "MappingHandler",
    # Errors
    "MappingError",
    "NoMatchingModelsError",
    # Convenience functions
    "map_schemas",
]


class MappingError(Exception):
    """Base error for mapping failures."""


class NoMatchingModelsError(MappingError):
    """No local models match the external schema."""

    def __init__(self, external_fields: List[str]):
        self.external_fields = external_fields
        super().__init__(
            f"No local models match external schema fields: {external_fields[:5]}..."
        )


def map_schemas(
    external_schema: Dict,
    local_models: List["LocalModel"],
    project_context: Optional["ProjectContext"] = None,
) -> SchemaMapping:
    """
    Convenience function to map external schema to local models.

    Args:
        external_schema: External API schema
        local_models: List of local models from discovery
        project_context: Optional project context

    Returns:
        SchemaMapping with suggested field mappings

    Raises:
        MappingError: If mapping fails
        NoMatchingModelsError: If no models match
    """
    mapper = SchemaMapper(project_context=project_context)
    return mapper.map(external_schema, local_models)
