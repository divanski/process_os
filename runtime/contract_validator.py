"""
ProcessOS Contract Validator

Sprint 3, Story S3-002: Agent Contract Validation (Strict Schema)
Validates agent outputs against strict JSON schema. No leniency - fail fast, fail clear.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

import jsonschema
from jsonschema import Draft202012Validator

__all__ = [
    "ContractValidator",
    "ValidationError",
]


class ValidationError(Exception):
    """Raised when agent output fails schema validation.

    Attributes:
        message: Human-readable error description
        field: The field that failed validation (if applicable)
        schema_path: JSON path in schema where validation failed
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        schema_path: Optional[str] = None
    ):
        self.field = field
        self.schema_path = schema_path
        super().__init__(message)


class ContractValidator:
    """Validates agent outputs against the agent-output schema.

    Enforces strict validation with additionalProperties: false.
    Invalid output fails immediately with clear error message.
    """

    # Default schema path relative to this file
    DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "agent-output.schema.json"

    def __init__(self, schema_path: Optional[Path] = None):
        """Initialize validator with schema.

        Args:
            schema_path: Optional path to schema file. Uses default if not provided.

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        if schema_path is None:
            schema_path = self.DEFAULT_SCHEMA_PATH

        with open(schema_path, "r") as f:
            self.schema = json.load(f)

        # Create validator with strict settings
        self._validator = Draft202012Validator(self.schema)

    def validate(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate agent output against schema.

        Args:
            output: Agent output dict to validate

        Returns:
            The validated output (unchanged if valid)

        Raises:
            ValidationError: If output doesn't match schema
        """
        errors = list(self._validator.iter_errors(output))

        if errors:
            # Get the most relevant error
            error = errors[0]

            # Extract field name from error path
            field = None
            if error.absolute_path:
                field = str(error.absolute_path[-1]) if error.absolute_path else None
            elif error.validator == "required":
                # Extract missing field from "required" error
                field = self._extract_missing_field(error)
            elif error.validator == "additionalProperties":
                # Extract extra field name
                field = self._extract_extra_field(error, output)

            # Build schema path
            schema_path = None
            if error.schema_path:
                schema_path = "$." + ".".join(str(p) for p in error.schema_path)

            # Create clear error message
            message = self._format_error_message(error, field)

            raise ValidationError(message, field=field, schema_path=schema_path)

        return output

    def _extract_missing_field(self, error: jsonschema.ValidationError) -> Optional[str]:
        """Extract missing field name from 'required' validation error."""
        # error.message is like "'decision' is a required property"
        if "is a required property" in error.message:
            # Extract field name from quotes
            parts = error.message.split("'")
            if len(parts) >= 2:
                return parts[1]
        return None

    def _extract_extra_field(
        self,
        error: jsonschema.ValidationError,
        output: Dict[str, Any]
    ) -> Optional[str]:
        """Extract extra field name from 'additionalProperties' error."""
        # error.message mentions the extra field
        if "Additional properties are not allowed" in error.message:
            # Find which fields in output aren't in schema
            schema_props = set(self.schema.get("properties", {}).keys())
            output_props = set(output.keys())
            extra = output_props - schema_props
            if extra:
                return list(extra)[0]
        return None

    def _format_error_message(
        self,
        error: jsonschema.ValidationError,
        field: Optional[str]
    ) -> str:
        """Format a clear, actionable error message."""
        if error.validator == "required":
            return f"Missing required field: '{field}'"

        if error.validator == "additionalProperties":
            return f"Extra field not allowed: '{field}' (strict mode rejects additional properties)"

        if error.validator == "enum":
            allowed = error.schema.get("enum", [])
            return f"Invalid value for '{field}': must be one of {allowed}"

        if error.validator == "minLength":
            return f"Field '{field}' cannot be empty (minLength: 1)"

        if error.validator == "type":
            expected = error.schema.get("type")
            return f"Invalid type for '{field}': expected {expected}"

        # Fallback to jsonschema's message
        return f"Validation failed: {error.message}"
