"""
ProcessOS Mapping Inference Module

Semantic similarity matching and type transformation inference.
"""

import re
from typing import Dict, List, Optional, Tuple

from .types import Transformation


# Common field name synonyms for semantic matching
FIELD_SYNONYMS = {
    "name": ["name", "title", "label", "display_name", "full_name", "customer_name", "client_name"],
    "email": ["email", "email_address", "e_mail", "contact_email", "mail"],
    "phone": ["phone", "phone_number", "telephone", "mobile", "cell", "contact_phone"],
    "address": ["address", "street", "location", "addr"],
    "id": ["id", "identifier", "key", "pk", "uuid", "guid"],
    "created": ["created", "created_at", "created_date", "date_created", "creation_date"],
    "updated": ["updated", "updated_at", "modified", "modified_at", "last_modified"],
    "price": ["price", "cost", "amount", "total", "value"],
    "quantity": ["quantity", "qty", "count", "amount", "num", "number"],
    "description": ["description", "desc", "summary", "details", "info"],
    "status": ["status", "state", "condition"],
    "type": ["type", "kind", "category", "class"],
}

# Type compatibility mappings
TYPE_COMPATIBILITY = {
    ("string", "CharField"): (True, None),
    ("string", "TextField"): (True, None),
    ("string", "EmailField"): (True, None),
    ("string", "IntegerField"): (True, "int"),
    ("string", "integer"): (True, "int"),
    ("string", "int"): (True, "int"),
    ("string", "DecimalField"): (True, "decimal"),
    ("string", "FloatField"): (True, "float"),
    ("string", "float"): (True, "float"),
    ("string", "BooleanField"): (True, "bool"),
    ("string", "boolean"): (True, "bool"),
    ("string", "bool"): (True, "bool"),
    ("string", "DateTimeField"): (True, "datetime"),
    ("string", "DateField"): (True, "date"),
    ("integer", "IntegerField"): (True, None),
    ("integer", "integer"): (True, None),
    ("integer", "CharField"): (True, "str"),
    ("integer", "string"): (True, "str"),
    ("integer", "DecimalField"): (True, "decimal"),
    ("number", "DecimalField"): (True, None),
    ("number", "FloatField"): (True, None),
    ("number", "IntegerField"): (True, "int"),
    ("boolean", "BooleanField"): (True, None),
    ("boolean", "boolean"): (True, None),
    ("boolean", "CharField"): (True, "str"),
    ("array", "JSONField"): (True, None),
    ("array", "ArrayField"): (True, None),
    ("object", "JSONField"): (True, None),
}


class SemanticMatcher:
    """
    Matches field names using semantic similarity.

    Uses:
    - Exact matching
    - Normalized name matching (case, separator normalization)
    - Synonym-based matching
    - Partial matching
    """

    def __init__(self, synonyms: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the semantic matcher.

        Args:
            synonyms: Optional custom synonym dictionary
        """
        self.synonyms = synonyms or FIELD_SYNONYMS

    def calculate_similarity(self, field1: str, field2: str) -> float:
        """
        Calculate similarity score between two field names.

        Args:
            field1: First field name
            field2: Second field name

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize names
        norm1 = self._normalize_name(field1)
        norm2 = self._normalize_name(field2)

        # Exact match after normalization
        if norm1 == norm2:
            return 1.0

        # Check synonym groups
        group1 = self._find_synonym_group(norm1)
        group2 = self._find_synonym_group(norm2)

        if group1 and group2 and group1 == group2:
            return 0.9

        if group1 and norm2 in self.synonyms.get(group1, []):
            return 0.85

        if group2 and norm1 in self.synonyms.get(group2, []):
            return 0.85

        # Partial matching (one contains the other)
        if norm1 in norm2 or norm2 in norm1:
            return 0.7

        # Token overlap
        tokens1 = set(self._tokenize(norm1))
        tokens2 = set(self._tokenize(norm2))

        if tokens1 and tokens2:
            overlap = len(tokens1 & tokens2)
            total = len(tokens1 | tokens2)
            if total > 0:
                return 0.6 * (overlap / total)

        return 0.0

    def find_best_match(
        self,
        field_name: str,
        candidates: List[str],
        threshold: float = 0.5,
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching candidate for a field name.

        Args:
            field_name: Field name to match
            candidates: List of candidate field names
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (best_match, score) or None if no match above threshold
        """
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            score = self.calculate_similarity(field_name, candidate)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate

        if best_match:
            return (best_match, best_score)
        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize a field name for comparison."""
        # Convert camelCase to snake_case
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        # Convert to lowercase
        name = name.lower()
        # Remove common prefixes/suffixes
        name = re.sub(r'^(get_|set_|is_|has_)', '', name)
        name = re.sub(r'(_field|_id|_fk)$', '', name)
        # Replace multiple underscores with single
        name = re.sub(r'_+', '_', name)
        # Strip leading/trailing underscores
        name = name.strip('_')
        return name

    def _find_synonym_group(self, name: str) -> Optional[str]:
        """Find which synonym group a name belongs to."""
        for group, synonyms in self.synonyms.items():
            normalized_synonyms = [self._normalize_name(s) for s in synonyms]
            if name in normalized_synonyms or name == group:
                return group
        return None

    def _tokenize(self, name: str) -> List[str]:
        """Tokenize a name into words."""
        return [t for t in re.split(r'[_\s]+', name) if t]


class TypeTransformer:
    """
    Suggests type transformations between external and local types.
    """

    def __init__(
        self,
        compatibility_map: Optional[Dict[Tuple[str, str], Tuple[bool, Optional[str]]]] = None,
    ):
        """
        Initialize the type transformer.

        Args:
            compatibility_map: Optional custom type compatibility map
        """
        self.compatibility_map = compatibility_map or TYPE_COMPATIBILITY

    def suggest_transformation(
        self,
        external_type: str,
        local_type: str,
        external_format: Optional[str] = None,
    ) -> Optional[Transformation]:
        """
        Suggest a transformation between types.

        Args:
            external_type: External API type
            local_type: Local model field type
            external_format: Optional format hint (e.g., 'ISO8601')

        Returns:
            Transformation or None if no transformation needed
        """
        # Normalize types
        ext_type = self._normalize_type(external_type)
        self._normalize_type(local_type)

        # Check if types are directly compatible
        key = (ext_type, local_type)
        if key in self.compatibility_map:
            compatible, transform = self.compatibility_map[key]
            if compatible and transform:
                return self._create_transformation(transform, external_format)
            return None  # Compatible, no transformation needed

        # Check normalized key
        for (k_ext, k_loc), (compatible, transform) in self.compatibility_map.items():
            if self._normalize_type(k_ext) == ext_type and k_loc.lower() in local_type.lower():
                if compatible and transform:
                    return self._create_transformation(transform, external_format)
                return None

        # Unknown type combination - suggest manual mapping
        return Transformation(
            type="manual",
            expression=f"convert({ext_type} -> {local_type})",
            description=f"Manual conversion needed from {ext_type} to {local_type}",
        )

    def _normalize_type(self, type_str: str) -> str:
        """Normalize a type string."""
        type_str = type_str.lower()
        # Map common variations
        if type_str in ["str", "text", "varchar"]:
            return "string"
        if type_str in ["int", "bigint", "smallint"]:
            return "integer"
        if type_str in ["float", "double", "decimal"]:
            return "number"
        if type_str in ["bool"]:
            return "boolean"
        if type_str in ["list", "[]"]:
            return "array"
        if type_str in ["dict", "map", "hash"]:
            return "object"
        return type_str

    def _create_transformation(
        self,
        transform_type: str,
        format_hint: Optional[str] = None,
    ) -> Transformation:
        """Create a transformation object."""
        if transform_type == "int":
            return Transformation(
                type="type_cast",
                expression="int(value)",
                description="Convert string to integer",
            )
        elif transform_type == "float":
            return Transformation(
                type="type_cast",
                expression="float(value)",
                description="Convert to floating point number",
            )
        elif transform_type == "decimal":
            return Transformation(
                type="type_cast",
                expression="Decimal(value)",
                description="Convert to decimal number",
            )
        elif transform_type == "bool":
            return Transformation(
                type="type_cast",
                expression="bool(value) if value not in ['false', '0', ''] else False",
                description="Convert string to boolean",
            )
        elif transform_type == "str":
            return Transformation(
                type="type_cast",
                expression="str(value)",
                description="Convert to string",
            )
        elif transform_type == "datetime":
            if format_hint == "ISO8601":
                return Transformation(
                    type="date_format",
                    expression="datetime.fromisoformat(value)",
                    description="Parse ISO8601 datetime string",
                )
            return Transformation(
                type="date_format",
                expression="parse_datetime(value)",
                description="Parse datetime string",
            )
        elif transform_type == "date":
            return Transformation(
                type="date_format",
                expression="parse_date(value)",
                description="Parse date string",
            )

        return Transformation(
            type="custom",
            expression=f"{transform_type}(value)",
            description=f"Apply {transform_type} transformation",
        )
