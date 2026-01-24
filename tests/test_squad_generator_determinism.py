"""
ProcessOS Squad Generator Determinism Tests

Tests for SN-002 and SN-009:
- Same input = byte-identical outputs
- Stable ordering
- No timestamps in generated content
"""

import pytest
import sys
import hashlib
import tempfile
from pathlib import Path

# Add process_os to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from process_os.generators.command_parser import CommandParser
from process_os.generators.squad_generator import SquadGenerator, SquadBundle


class TestSquadGeneratorDeterminism:
    """Determinism tests for squad generator."""

    def test_same_request_same_playbook_yaml(self):
        """Same request produces identical playbook YAML."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier DHL Express")

        bundle1 = generator.generate(request)
        bundle2 = generator.generate(request)

        yaml1 = bundle1.playbook.to_yaml()
        yaml2 = bundle2.playbook.to_yaml()

        assert yaml1 == yaml2, "Playbook YAML must be byte-identical"

    def test_same_request_same_agent_cards(self):
        """Same request produces identical agent cards."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier FedEx")

        bundle1 = generator.generate(request)
        bundle2 = generator.generate(request)

        # Compare each agent
        assert len(bundle1.agents) == len(bundle2.agents)

        for agent1, agent2 in zip(
            sorted(bundle1.agents, key=lambda a: a.agent_id),
            sorted(bundle2.agents, key=lambda a: a.agent_id)
        ):
            yaml1 = agent1.to_yaml()
            yaml2 = agent2.to_yaml()
            assert yaml1 == yaml2, f"Agent {agent1.agent_id} YAML must be byte-identical"

    def test_same_request_same_templates(self):
        """Same request produces identical templates."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("create API mapping for Shippo")

        bundle1 = generator.generate(request)
        bundle2 = generator.generate(request)

        assert bundle1.templates == bundle2.templates

    def test_same_request_same_manifest_hashes(self):
        """Same request produces identical manifest hashes."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier UPS")

        bundle1 = generator.generate(request)
        bundle2 = generator.generate(request)

        manifest1 = bundle1.get_manifest()
        manifest2 = bundle2.get_manifest()

        assert manifest1["playbook_sha256"] == manifest2["playbook_sha256"]

        for a1, a2 in zip(manifest1["agents"], manifest2["agents"]):
            assert a1["sha256"] == a2["sha256"]

    def test_written_bundle_byte_identical(self):
        """Written bundle files are byte-identical across runs."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                bundle1 = generator.generate(request)
                bundle2 = generator.generate(request)

                files1 = generator.write_bundle(bundle1, Path(tmpdir1))
                files2 = generator.write_bundle(bundle2, Path(tmpdir2))

                # Compare file contents by hash
                for key in files1:
                    if key in files2:
                        content1 = Path(files1[key]).read_text()
                        content2 = Path(files2[key]).read_text()

                        hash1 = hashlib.sha256(content1.encode()).hexdigest()
                        hash2 = hashlib.sha256(content2.encode()).hexdigest()

                        assert hash1 == hash2, f"File {key} must be byte-identical"


class TestSquadGeneratorOrdering:
    """Ordering stability tests."""

    def test_agents_sorted_by_id(self):
        """Agents in manifest are sorted by ID."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")
        bundle = generator.generate(request)

        manifest = bundle.get_manifest()
        agent_ids = [a["agent_id"] for a in manifest["agents"]]

        assert agent_ids == sorted(agent_ids)

    def test_templates_sorted_by_name(self):
        """Templates in manifest are sorted by name."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")
        bundle = generator.generate(request)

        manifest = bundle.get_manifest()
        template_names = [t["name"] for t in manifest["templates"]]

        assert template_names == sorted(template_names)

    def test_steps_ordered_by_sequence(self):
        """Playbook steps are ordered by sequence number."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")
        bundle = generator.generate(request)

        sequences = [step.sequence for step in bundle.playbook.steps]
        assert sequences == sorted(sequences)


class TestSquadGeneratorNoTimestamps:
    """Verify no timestamps in generated content."""

    def test_playbook_no_timestamp(self):
        """Playbook YAML contains no timestamps."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")
        bundle = generator.generate(request)

        yaml_content = bundle.playbook.to_yaml()

        # Check for common timestamp patterns
        timestamp_patterns = [
            "2026-",
            "2025-",
            "2024-",
            "T00:",
            "T01:",
            "timestamp",
            "created_at",
            "updated_at",
        ]

        for pattern in timestamp_patterns:
            assert pattern not in yaml_content, f"Playbook should not contain '{pattern}'"

    def test_agent_cards_no_timestamp(self):
        """Agent cards contain no timestamps."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse("integrate courier TestCourier")
        bundle = generator.generate(request)

        for agent in bundle.agents:
            yaml_content = agent.to_yaml()

            timestamp_patterns = ["2026-", "2025-", "timestamp", "created_at"]
            for pattern in timestamp_patterns:
                assert pattern not in yaml_content, f"Agent should not contain '{pattern}'"


class TestSquadGeneratorCommandTypes:
    """Test different command types produce valid bundles."""

    @pytest.mark.parametrize("command,expected_type", [
        ("integrate courier DHL", "courier_integration"),
        ("add courier FedEx", "courier_integration"),
        ("map API for Stripe", "api_mapping"),
        ("create API mapping for PayPal", "api_mapping"),
        ("detect fraud patterns", "detection_rules"),
        ("do custom thing for Target", "custom"),
    ])
    def test_command_type_detection(self, command, expected_type):
        """Different commands produce correct types."""
        parser = CommandParser()
        generator = SquadGenerator()

        request = parser.parse(command)
        bundle = generator.generate(request)

        assert request.command_type == expected_type
        assert bundle.playbook is not None
        assert len(bundle.agents) > 0
