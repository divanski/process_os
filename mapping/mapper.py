"""
ProcessOS Schema Mapper Module

Maps external API schemas to local models using semantic matching.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import uuid

from .types import (
    FieldMapping,
    SchemaMapping,
    UnmappedField,
)
from .inference import SemanticMatcher, TypeTransformer

if TYPE_CHECKING:
    from ..discovery import LocalModel, ProjectContext


class SchemaMapper:
    """
    Maps external API schemas to local models.

    Uses semantic similarity matching for field names
    and suggests type transformations where needed.
    """

    # Minimum confidence threshold for auto-mapping
    MIN_CONFIDENCE = 0.5

    def __init__(
        self,
        project_context: Optional["ProjectContext"] = None,
        matcher: Optional[SemanticMatcher] = None,
        transformer: Optional[TypeTransformer] = None,
    ):
        """
        Initialize the SchemaMapper.

        Args:
            project_context: Optional project context with discovered models
            matcher: Optional custom semantic matcher
            transformer: Optional custom type transformer
        """
        self.project_context = project_context
        self.matcher = matcher or SemanticMatcher()
        self.transformer = transformer or TypeTransformer()

    def map(
        self,
        external_schema: Dict[str, Any],
        local_models: List["LocalModel"],
        intent_id: str = "",
        materials_id: str = "",
        endpoint: str = "",
    ) -> SchemaMapping:
        """
        Map external schema to local models.

        Args:
            external_schema: External API schema (JSON Schema format)
            local_models: List of local models from discovery
            intent_id: ID of the intent this mapping is for
            materials_id: ID of the materials collection
            endpoint: Endpoint this schema is from

        Returns:
            SchemaMapping with suggested field mappings
        """
        field_mappings = []
        unmapped_external = []
        unmapped_local = []

        # Extract fields from external schema
        external_fields = self._extract_fields(external_schema)

        # Build candidate pool from all local models
        local_candidates = self._build_candidate_pool(local_models)

        # Track which local fields have been mapped
        mapped_local_fields = set()

        # Map each external field
        for field_path, field_info in external_fields.items():
            mapping = self._find_best_mapping(
                field_path=field_path,
                field_info=field_info,
                local_candidates=local_candidates,
                endpoint=endpoint,
            )

            if mapping:
                field_mappings.append(mapping)
                mapped_local_fields.add((mapping.local_model, mapping.local_field))
            else:
                unmapped_external.append(
                    UnmappedField(
                        source="external",
                        field_path=field_path,
                        field_type=field_info.get("type", "unknown"),
                        reason="No matching local field found",
                    )
                )

        # Find unmapped local fields
        for model in local_models:
            for field in model.fields:
                if (model.name, field.name) not in mapped_local_fields:
                    unmapped_local.append(
                        UnmappedField(
                            source="local",
                            field_path=f"{model.name}.{field.name}",
                            field_type=field.field_type,
                            reason="No matching external field found",
                        )
                    )

        return SchemaMapping(
            intent_id=intent_id or f"intent-{uuid.uuid4().hex[:8]}",
            materials_id=materials_id or f"mat-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(),
            field_mappings=field_mappings,
            unmapped_external=unmapped_external,
            unmapped_local=unmapped_local,
        )

    def suggest_mapping(
        self,
        external_field: str,
        external_type: str,
        local_models: List["LocalModel"],
        endpoint: str = "",
    ) -> Optional[FieldMapping]:
        """
        Suggest mapping for a single external field.

        Args:
            external_field: External field path
            external_type: External field type
            local_models: List of local models
            endpoint: Endpoint this field is from

        Returns:
            Suggested FieldMapping or None
        """
        local_candidates = self._build_candidate_pool(local_models)

        return self._find_best_mapping(
            field_path=external_field,
            field_info={"type": external_type},
            local_candidates=local_candidates,
            endpoint=endpoint,
        )

    def _extract_fields(
        self,
        schema: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract all fields from a JSON Schema.

        Args:
            schema: JSON Schema dict
            prefix: Path prefix for nested fields

        Returns:
            Dict of field_path -> field_info
        """
        fields = {}

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                field_path = f"{prefix}.{prop_name}" if prefix else prop_name

                # Check if this is a nested object
                prop_type = prop_schema.get("type", "string")
                if prop_type == "object" and "properties" in prop_schema:
                    # Recurse into nested object
                    nested_fields = self._extract_fields(prop_schema, field_path)
                    fields.update(nested_fields)
                elif prop_type == "array":
                    # Handle array items
                    items = prop_schema.get("items", {})
                    if items.get("type") == "object" and "properties" in items:
                        nested_fields = self._extract_fields(items, f"{field_path}[]")
                        fields.update(nested_fields)
                    fields[field_path] = prop_schema
                else:
                    fields[field_path] = prop_schema

        return fields

    def _build_candidate_pool(
        self,
        models: List["LocalModel"],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build pool of candidate local fields for matching.

        Args:
            models: List of local models

        Returns:
            Dict of field_name -> list of candidate info dicts
        """
        candidates = {}

        for model in models:
            for field in model.fields:
                if field.name not in candidates:
                    candidates[field.name] = []

                candidates[field.name].append({
                    "model": model.name,
                    "field": field.name,
                    "type": field.field_type,
                    "nullable": field.nullable,
                })

        return candidates

    def _find_best_mapping(
        self,
        field_path: str,
        field_info: Dict[str, Any],
        local_candidates: Dict[str, List[Dict[str, Any]]],
        endpoint: str = "",
    ) -> Optional[FieldMapping]:
        """
        Find the best mapping for an external field.

        Args:
            field_path: External field path
            field_info: External field schema info
            local_candidates: Pool of local field candidates
            endpoint: Endpoint this field is from

        Returns:
            Best FieldMapping or None
        """
        # Extract just the field name from path
        field_name = field_path.split(".")[-1].rstrip("[]")
        external_type = field_info.get("type", "string")

        # Find best match among all candidate fields
        best_match = None
        best_score = 0.0
        best_candidate = None

        for local_field_name, candidates in local_candidates.items():
            score = self.matcher.calculate_similarity(field_name, local_field_name)

            if score > best_score and score >= self.MIN_CONFIDENCE:
                best_score = score
                best_match = local_field_name
                # Pick first candidate (could be smarter about this)
                best_candidate = candidates[0]

        if best_match and best_candidate:
            # Check if transformation is needed
            transformation = self.transformer.suggest_transformation(
                external_type=external_type,
                local_type=best_candidate["type"],
                external_format=field_info.get("format"),
            )

            return FieldMapping(
                id=f"fm-{uuid.uuid4().hex[:8]}",
                external_endpoint=endpoint,
                external_field_path=field_path,
                external_type=external_type,
                local_model=best_candidate["model"],
                local_field=best_candidate["field"],
                local_type=best_candidate["type"],
                transformation=transformation,
                confidence=best_score,
                reasoning=self._generate_reasoning(field_name, best_match, best_score),
            )

        return None

    def _generate_reasoning(
        self,
        external_field: str,
        local_field: str,
        score: float,
    ) -> str:
        """Generate human-readable reasoning for a mapping."""
        if score >= 0.95:
            return f"Exact match: '{external_field}' -> '{local_field}'"
        elif score >= 0.85:
            return f"Synonym match: '{external_field}' is semantically equivalent to '{local_field}'"
        elif score >= 0.7:
            return f"Partial match: '{external_field}' contains or is contained by '{local_field}'"
        else:
            return f"Token overlap: '{external_field}' shares common terms with '{local_field}'"

    def get_unmapped(self, mapping: SchemaMapping) -> Dict[str, List[UnmappedField]]:
        """
        Get unmapped fields from a mapping.

        Args:
            mapping: SchemaMapping to analyze

        Returns:
            Dict with 'external' and 'local' unmapped field lists
        """
        return {
            "external": mapping.unmapped_external,
            "local": mapping.unmapped_local,
        }
