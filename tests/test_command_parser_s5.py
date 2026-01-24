"""
ProcessOS Command Parser Tests (Sprint 5)

Tests for S5-002: Command parsing into TaskRequest.
"""

import json
from pathlib import Path

import pytest

from process_os.commands import CommandParser, TaskRequest


class TestCommandParserBasics:
    """Basic command parsing tests."""

    def test_parse_integrate_command(self):
        """Parse integration command."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        assert request.intent == "integrate"
        assert request.target.type == "courier"
        assert "dhl" in request.target.identifier.lower()

    def test_parse_map_api_command(self):
        """Parse API mapping command."""
        parser = CommandParser()
        request = parser.parse("map API for Stripe", include_timestamp=False)

        assert request.intent == "map_api"
        assert request.target.type == "api"
        assert "stripe" in request.target.identifier.lower()

    def test_parse_detect_command(self):
        """Parse detection command."""
        parser = CommandParser()
        request = parser.parse("detect fraud patterns", include_timestamp=False)

        assert request.intent == "detect"

    def test_parse_custom_command(self):
        """Parse custom command falls back to custom intent."""
        parser = CommandParser()
        request = parser.parse("do something special with Widget", include_timestamp=False)

        assert request.intent == "custom"


class TestCommandParserDeterminism:
    """Command parser determinism tests."""

    def test_same_command_same_id(self):
        """Same command text produces same command_id."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL", include_timestamp=False)
        request2 = parser.parse("integrate courier DHL", include_timestamp=False)

        assert request1.command_id == request2.command_id

    def test_same_command_same_json(self):
        """Same command produces identical JSON (without timestamp)."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL", include_timestamp=False)
        request2 = parser.parse("integrate courier DHL", include_timestamp=False)

        json1 = request1.to_json()
        json2 = request2.to_json()

        assert json1 == json2

    def test_different_commands_different_ids(self):
        """Different commands produce different IDs."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL", include_timestamp=False)
        request2 = parser.parse("integrate courier FedEx", include_timestamp=False)

        assert request1.command_id != request2.command_id

    def test_case_insensitive_id_generation(self):
        """Command ID is case-insensitive."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL", include_timestamp=False)
        request2 = parser.parse("INTEGRATE COURIER DHL", include_timestamp=False)

        assert request1.command_id == request2.command_id


class TestTaskRequestSerialization:
    """TaskRequest serialization tests."""

    def test_to_dict_sorted_keys(self):
        """to_dict produces sorted keys."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        d = request.to_dict()

        # Check top-level keys are sorted
        keys = list(d.keys())
        assert keys == sorted(keys)

    def test_to_json_deterministic(self):
        """to_json produces deterministic output."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        json1 = request.to_json()
        json2 = request.to_json()

        assert json1 == json2

    def test_from_dict_roundtrip(self):
        """Can roundtrip through dict."""
        parser = CommandParser()
        original = parser.parse("integrate courier DHL", include_timestamp=False)

        d = original.to_dict()
        restored = TaskRequest.from_dict(d)

        assert restored.command_id == original.command_id
        assert restored.intent == original.intent
        assert restored.target.name == original.target.name

    def test_from_json_roundtrip(self):
        """Can roundtrip through JSON."""
        parser = CommandParser()
        original = parser.parse("integrate courier DHL", include_timestamp=False)

        json_str = original.to_json()
        restored = TaskRequest.from_json(json_str)

        assert restored.command_id == original.command_id


class TestWorkspaceIdGeneration:
    """Workspace ID generation tests."""

    def test_workspace_id_derived_from_command_id(self):
        """Workspace ID is derived from command ID."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        workspace_id = request.get_workspace_id()

        # Same hash, different prefix
        assert workspace_id.startswith("ws-")
        assert workspace_id[3:] == request.command_id[4:]

    def test_same_command_same_workspace_id(self):
        """Same command produces same workspace ID."""
        parser = CommandParser()

        request1 = parser.parse("integrate courier DHL", include_timestamp=False)
        request2 = parser.parse("integrate courier DHL", include_timestamp=False)

        assert request1.get_workspace_id() == request2.get_workspace_id()


class TestPriorityDetection:
    """Priority detection tests."""

    def test_critical_priority(self):
        """Detects critical priority keywords."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL - urgent", include_timestamp=False)

        assert request.parameters.priority == "critical"

    def test_high_priority(self):
        """Detects high priority keywords."""
        parser = CommandParser()
        request = parser.parse("important: integrate courier DHL", include_timestamp=False)

        assert request.parameters.priority == "high"

    def test_low_priority(self):
        """Detects low priority keywords."""
        parser = CommandParser()
        request = parser.parse("whenever: integrate courier DHL", include_timestamp=False)

        assert request.parameters.priority == "low"

    def test_default_medium_priority(self):
        """Default priority is medium."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        assert request.parameters.priority == "medium"


class TestCapabilityExtraction:
    """Capability extraction tests."""

    def test_tracking_capability(self):
        """Extracts tracking capability."""
        parser = CommandParser()
        request = parser.parse(
            "integrate courier DHL with tracking",
            include_timestamp=False,
        )

        assert "shipment_tracking" in request.parameters.capabilities

    def test_label_capability(self):
        """Extracts label capability."""
        parser = CommandParser()
        request = parser.parse(
            "integrate courier DHL with label generation",
            include_timestamp=False,
        )

        assert "label_generation" in request.parameters.capabilities

    def test_multiple_capabilities(self):
        """Extracts multiple capabilities."""
        parser = CommandParser()
        request = parser.parse(
            "integrate courier DHL with tracking and labels and rates",
            include_timestamp=False,
        )

        assert "shipment_tracking" in request.parameters.capabilities
        assert "label_generation" in request.parameters.capabilities
        assert "rate_calculation" in request.parameters.capabilities


class TestExampleCommands:
    """Test example commands match expected output."""

    def test_integrate_dhl_example(self):
        """Verify integrate DHL example."""
        example_path = (
            Path(__file__).parent.parent
            / "commands"
            / "examples"
            / "integrate_dhl.json"
        )

        if not example_path.exists():
            pytest.skip("Example file not found")

        with open(example_path) as f:
            example = json.load(f)

        parser = CommandParser()
        request = parser.parse(example["command"], include_timestamp=False)

        # Verify key fields match
        assert request.command_id == example["expected"]["command_id"]
        assert request.intent == example["expected"]["intent"]
        assert request.target.type == example["expected"]["target"]["type"]

    def test_map_stripe_api_example(self):
        """Verify map Stripe API example."""
        example_path = (
            Path(__file__).parent.parent
            / "commands"
            / "examples"
            / "map_stripe_api.json"
        )

        if not example_path.exists():
            pytest.skip("Example file not found")

        with open(example_path) as f:
            example = json.load(f)

        parser = CommandParser()
        request = parser.parse(example["command"], include_timestamp=False)

        assert request.command_id == example["expected"]["command_id"]
        assert request.intent == example["expected"]["intent"]
