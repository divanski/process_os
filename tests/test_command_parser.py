"""
ProcessOS Command Parser Tests

Tests for SN-001: Command Parser
- Schema validation
- Deterministic parsing
- Different command types
"""

import pytest
import sys
from pathlib import Path

# Add process_os to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from process_os.generators.command_parser import CommandParser, SquadRequest


class TestCommandParserBasics:
    """Basic command parser tests."""

    def test_parse_courier_integration_command(self):
        """Parse a courier integration command."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL Express")

        assert request.command_type == "courier_integration"
        assert request.target["name"] == "DHL Express"
        assert request.target["identifier"] == "dhl-express"

    def test_parse_api_mapping_command(self):
        """Parse an API mapping command."""
        parser = CommandParser()
        request = parser.parse("map API for Shippo")

        assert request.command_type == "api_mapping"
        assert "shippo" in request.target["identifier"].lower()

    def test_parse_detection_rules_command(self):
        """Parse a detection rules command."""
        parser = CommandParser()
        request = parser.parse("create detection for fraudulent shipments")

        assert request.command_type == "detection_rules"

    def test_parse_custom_command(self):
        """Parse a custom/unrecognized command."""
        parser = CommandParser()
        request = parser.parse("do something with 'MyTarget'")

        assert request.command_type == "custom"
        assert request.target["name"] == "MyTarget"


class TestCommandParserDeterminism:
    """Determinism tests for command parser."""

    def test_same_command_same_request_id(self):
        """Same command produces same request ID."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier FedEx")
        request2 = parser.parse("integrate courier FedEx")

        assert request1.request_id == request2.request_id

    def test_same_command_same_json(self):
        """Same command produces identical JSON output."""
        parser = CommandParser()

        request1 = parser.parse("add courier UPS Ground")
        request2 = parser.parse("add courier UPS Ground")

        assert request1.to_json() == request2.to_json()

    def test_different_commands_different_ids(self):
        """Different commands produce different IDs."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL")
        request2 = parser.parse("integrate courier FedEx")

        assert request1.request_id != request2.request_id

    def test_case_insensitive_id_generation(self):
        """Request ID is case-insensitive."""
        parser = CommandParser()

        request1 = parser.parse("Integrate Courier DHL")
        request2 = parser.parse("integrate courier dhl")

        assert request1.request_id == request2.request_id


class TestCommandParserValidation:
    """Schema validation tests."""

    def test_empty_command_raises_error(self):
        """Empty command raises ValueError."""
        parser = CommandParser()

        with pytest.raises(ValueError):
            parser.parse("")

    def test_whitespace_only_raises_error(self):
        """Whitespace-only command raises ValueError."""
        parser = CommandParser()

        with pytest.raises(ValueError):
            parser.parse("   ")

    def test_generated_identifier_is_valid(self):
        """Generated identifier matches pattern."""
        parser = CommandParser()
        request = parser.parse("integrate courier 'My Special Courier 123!'")

        # Should be kebab-case, lowercase, alphanumeric
        identifier = request.target["identifier"]
        assert identifier.islower() or "-" in identifier
        assert not any(c.isupper() for c in identifier)


class TestCommandParserParameters:
    """Parameter extraction tests."""

    def test_priority_detection_critical(self):
        """Detect critical priority keywords."""
        parser = CommandParser()
        request = parser.parse("urgent: integrate courier DHL")

        assert request.parameters["priority"] == "critical"

    def test_priority_detection_high(self):
        """Detect high priority keywords."""
        parser = CommandParser()
        request = parser.parse("important courier integration for FedEx")

        assert request.parameters["priority"] == "high"

    def test_capability_detection(self):
        """Detect capabilities from command."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL with tracking and label generation")

        assert "shipment_tracking" in request.parameters["capabilities"]
        assert "label_generation" in request.parameters["capabilities"]

    def test_default_capabilities(self):
        """Default capabilities when none detected."""
        parser = CommandParser()
        request = parser.parse("integrate courier NewCourier")

        # Should have default capabilities
        assert len(request.parameters["capabilities"]) > 0


class TestSquadRequestSerialization:
    """SquadRequest serialization tests."""

    def test_to_dict_sorted_keys(self):
        """to_dict produces sorted keys."""
        request = SquadRequest(
            request_id="req-123456789012",
            command_type="courier_integration",
            target={"name": "Test", "identifier": "test"},
            parameters={"z_param": 1, "a_param": 2},
        )

        d = request.to_dict()
        keys = list(d.keys())

        assert keys == sorted(keys)

    def test_to_json_deterministic(self):
        """to_json produces deterministic output."""
        request = SquadRequest(
            request_id="req-123456789012",
            command_type="custom",
            target={"name": "Test", "identifier": "test"},
            parameters={},
        )

        json1 = request.to_json()
        json2 = request.to_json()

        assert json1 == json2

    def test_parse_json_roundtrip(self):
        """JSON roundtrip preserves data."""
        parser = CommandParser()
        original = parser.parse("integrate courier TestCourier")

        json_str = original.to_json()
        restored = parser.parse_json(json_str)

        assert restored.request_id == original.request_id
        assert restored.command_type == original.command_type
        assert restored.target == original.target
