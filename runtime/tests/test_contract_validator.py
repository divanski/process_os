"""
ProcessOS Contract Validator Tests

Sprint 3, Story S3-002: Agent Contract Validation (Strict Schema)
TDD tests for ContractValidator with strict schema enforcement.
"""

import pytest


class TestContractValidatorBasics:
    """Basic validation tests."""

    def test_validator_loads_schema(self):
        """ContractValidator loads schema from file."""
        from contract_validator import ContractValidator

        validator = ContractValidator()
        assert validator.schema is not None
        assert "properties" in validator.schema


class TestValidOutput:
    """Tests for AC1: Valid output passes validation."""

    def test_valid_output_with_required_fields(self):
        """Valid output with decision and reasoning passes."""
        from contract_validator import ContractValidator

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": "All checks passed"
        }

        result = validator.validate(output)

        assert result == output

    def test_valid_output_with_artifacts(self):
        """Valid output with optional artifacts passes."""
        from contract_validator import ContractValidator

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": "Generated report",
            "artifacts": [
                {"kind": "report", "content": "Report content here"}
            ]
        }

        result = validator.validate(output)

        assert result == output
        assert len(result["artifacts"]) == 1

    def test_valid_output_all_decision_types(self):
        """All valid decision types pass validation."""
        from contract_validator import ContractValidator

        validator = ContractValidator()

        for decision in ["proceed", "halt", "escalate"]:
            output = {
                "decision": decision,
                "reasoning": f"Decision: {decision}"
            }
            result = validator.validate(output)
            assert result["decision"] == decision


class TestMissingFields:
    """Tests for AC2: Missing required field fails."""

    def test_missing_decision_raises_error(self):
        """Missing 'decision' field raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "reasoning": "Some reasoning but no decision"
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(output)

        assert "decision" in str(exc_info.value).lower()

    def test_missing_reasoning_raises_error(self):
        """Missing 'reasoning' field raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed"
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(output)

        assert "reasoning" in str(exc_info.value).lower()

    def test_empty_reasoning_raises_error(self):
        """Empty reasoning (minLength: 1) raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": ""  # Empty string
        }

        with pytest.raises(ValidationError):
            validator.validate(output)

    def test_validation_error_includes_field_name(self):
        """ValidationError includes the field that failed."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {"reasoning": "Missing decision"}

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(output)

        error = exc_info.value
        assert hasattr(error, "field") or "decision" in str(error)


class TestExtraFields:
    """Tests for AC3: Extra fields fail validation (strict mode)."""

    def test_extra_field_raises_error(self):
        """Extra field not in schema raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": "Valid reasoning",
            "extra_field": "This should not be here"
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(output)

        assert "extra" in str(exc_info.value).lower() or "additional" in str(exc_info.value).lower()

    def test_strict_mode_rejects_typos(self):
        """Typo in field name (e.g., 'desicion') raises error."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "desicion": "proceed",  # Typo!
            "reasoning": "Valid reasoning"
        }

        with pytest.raises(ValidationError):
            validator.validate(output)


class TestInvalidValues:
    """Tests for invalid field values."""

    def test_invalid_decision_value_raises_error(self):
        """Decision not in enum raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "maybe",  # Not in enum
            "reasoning": "Valid reasoning"
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(output)

        assert "decision" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()

    def test_wrong_type_raises_error(self):
        """Wrong type for field raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": 12345  # Should be string
        }

        with pytest.raises(ValidationError):
            validator.validate(output)

    def test_invalid_artifact_structure(self):
        """Artifact missing required fields raises ValidationError."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": "Valid",
            "artifacts": [
                {"kind": "report"}  # Missing 'content'
            ]
        }

        with pytest.raises(ValidationError):
            validator.validate(output)

    def test_extra_field_in_artifact_raises_error(self):
        """Extra field inside artifact raises ValidationError (strict nested)."""
        from contract_validator import ContractValidator, ValidationError

        validator = ContractValidator()
        output = {
            "decision": "proceed",
            "reasoning": "Valid",
            "artifacts": [
                {
                    "kind": "report",
                    "content": "Report text",
                    "metadata": "extra field"  # Not allowed
                }
            ]
        }

        with pytest.raises(ValidationError):
            validator.validate(output)


class TestValidationErrorDetails:
    """Tests for ValidationError attributes."""

    def test_validation_error_has_message(self):
        """ValidationError has clear error message."""
        from contract_validator import ValidationError

        error = ValidationError("Test message", field="test_field")

        assert str(error) == "Test message"
        assert error.field == "test_field"

    def test_validation_error_has_schema_path(self):
        """ValidationError can include schema path."""
        from contract_validator import ValidationError

        error = ValidationError(
            "Field missing",
            field="decision",
            schema_path="$.properties.decision"
        )

        assert error.schema_path == "$.properties.decision"
