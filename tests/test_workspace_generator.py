"""
ProcessOS Workspace Generator Tests

Tests for S5-003: Workspace generation with determinism.
"""

import hashlib
import tempfile
from pathlib import Path

import pytest

from process_os.commands import CommandParser
from process_os.generators.workspace_generator import (
    Workspace,
    WorkspaceGenerator,
    WorkspaceManifest,
)


class TestWorkspaceGeneratorBasics:
    """Basic workspace generation tests."""

    def test_generate_creates_workspace(self):
        """Generator creates workspace from request."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert workspace.workspace_id == request.get_workspace_id()
        assert workspace.command_id == request.command_id

    def test_workspace_has_playbook(self):
        """Generated workspace has playbook."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert workspace.playbook is not None
        assert workspace.playbook.playbook_id.startswith("playbook-")

    def test_workspace_has_agents(self):
        """Generated workspace has agents."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.agents) > 0
        for agent in workspace.agents:
            assert agent.agent_id
            assert agent.name
            assert agent.role

    def test_workspace_has_templates(self):
        """Generated workspace has templates."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.templates) > 0

    def test_workspace_has_gates(self):
        """Generated workspace has gates."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.gates) > 0


class TestWorkspaceGeneratorDeterminism:
    """Workspace generator determinism tests."""

    def test_same_request_same_playbook_yaml(self):
        """Same request produces same playbook YAML."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()

        ws1 = generator.generate(request)
        ws2 = generator.generate(request)

        assert ws1.playbook.to_yaml() == ws2.playbook.to_yaml()

    def test_same_request_same_agent_cards(self):
        """Same request produces same agent cards."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()

        ws1 = generator.generate(request)
        ws2 = generator.generate(request)

        for a1, a2 in zip(
            sorted(ws1.agents, key=lambda a: a.agent_id),
            sorted(ws2.agents, key=lambda a: a.agent_id),
        ):
            assert a1.to_yaml() == a2.to_yaml()

    def test_same_request_same_templates(self):
        """Same request produces same templates."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()

        ws1 = generator.generate(request)
        ws2 = generator.generate(request)

        assert ws1.templates == ws2.templates

    def test_same_request_same_file_hashes(self):
        """Same request produces same file hashes."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()

        ws1 = generator.generate(request)
        ws2 = generator.generate(request)

        hashes1 = ws1.get_file_hashes()
        hashes2 = ws2.get_file_hashes()

        assert hashes1 == hashes2

    def test_written_workspace_byte_identical(self):
        """Written workspace files are byte-identical across runs."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        with tempfile.TemporaryDirectory() as tmp1:
            gen1 = WorkspaceGenerator(Path(tmp1))
            ws1 = gen1.generate(request)
            gen1.write_workspace(ws1)

            # Read playbook
            playbook1 = (
                Path(tmp1) / ws1.workspace_id / "playbook.yaml"
            ).read_text()

        with tempfile.TemporaryDirectory() as tmp2:
            gen2 = WorkspaceGenerator(Path(tmp2))
            ws2 = gen2.generate(request)
            gen2.write_workspace(ws2)

            playbook2 = (
                Path(tmp2) / ws2.workspace_id / "playbook.yaml"
            ).read_text()

        assert playbook1 == playbook2


class TestWorkspaceGeneratorIntents:
    """Tests for different intent types."""

    def test_integrate_intent_agents(self):
        """Integrate intent produces correct agents."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        agent_ids = [a.agent_id for a in workspace.agents]
        # Check that expected agent types are present
        assert any("intake-analyst" in aid for aid in agent_ids)
        assert any("mapper" in aid for aid in agent_ids)
        assert any("validator" in aid for aid in agent_ids)

    def test_map_api_intent_agents(self):
        """Map API intent produces correct agents."""
        parser = CommandParser()
        request = parser.parse("map API for Stripe", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        agent_ids = [a.agent_id for a in workspace.agents]
        assert any("schema-analyst" in aid for aid in agent_ids)
        assert any("field-mapper" in aid for aid in agent_ids)

    def test_detect_intent_agents(self):
        """Detect intent produces correct agents."""
        parser = CommandParser()
        request = parser.parse("detect fraud patterns", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        agent_ids = [a.agent_id for a in workspace.agents]
        assert any("pattern-analyst" in aid for aid in agent_ids)


class TestWorkspaceWriting:
    """Workspace writing tests."""

    def test_write_creates_directory_structure(self):
        """Writing workspace creates expected structure."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceGenerator(Path(tmpdir))
            workspace = generator.generate(request)
            workspace_dir = generator.write_workspace(workspace)

            # Check structure
            assert workspace_dir.exists()
            assert (workspace_dir / "playbook.yaml").exists()
            assert (workspace_dir / "manifest.yaml").exists()
            assert (workspace_dir / "agents").is_dir()
            assert (workspace_dir / "templates").is_dir()
            assert (workspace_dir / "gates").is_dir()
            assert (workspace_dir / "runs").is_dir()

    def test_write_creates_all_agents(self):
        """Writing workspace creates all agent files."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceGenerator(Path(tmpdir))
            workspace = generator.generate(request)
            workspace_dir = generator.write_workspace(workspace)

            agents_dir = workspace_dir / "agents"
            agent_files = list(agents_dir.glob("*.yaml"))

            assert len(agent_files) == len(workspace.agents)

    def test_write_creates_all_templates(self):
        """Writing workspace creates all template files."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceGenerator(Path(tmpdir))
            workspace = generator.generate(request)
            workspace_dir = generator.write_workspace(workspace)

            templates_dir = workspace_dir / "templates"
            template_files = list(templates_dir.glob("*.j2"))

            assert len(template_files) == len(workspace.templates)


class TestWorkspaceManifest:
    """Workspace manifest tests."""

    def test_manifest_contains_command_id(self):
        """Manifest contains command ID for traceability."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert workspace.manifest.command_id == request.command_id

    def test_manifest_contains_workspace_id(self):
        """Manifest contains workspace ID."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert workspace.manifest.workspace_id == workspace.workspace_id

    def test_manifest_contains_file_hashes(self):
        """Manifest contains file hashes."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.manifest.hashes) > 0
        assert "playbook.yaml" in workspace.manifest.hashes

    def test_manifest_to_yaml_deterministic(self):
        """Manifest YAML is deterministic."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()

        ws1 = generator.generate(request)
        ws2 = generator.generate(request)

        # Note: created_at will differ, so we compare structure
        assert ws1.manifest.command_id == ws2.manifest.command_id
        assert ws1.manifest.workspace_id == ws2.manifest.workspace_id
        assert ws1.manifest.hashes == ws2.manifest.hashes


class TestInboxGatesForCourierIntegrations:
    """Tests for inbox gates in courier integration playbooks."""

    def test_courier_integration_has_inbox_gate(self):
        """Courier integration playbook includes inbox gate."""
        parser = CommandParser()
        request = parser.parse("integrate courier FedEx", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.playbook.inbox_gates) == 1
        gate = workspace.playbook.inbox_gates[0]
        assert gate.integration_id == "fedex"

    def test_inbox_gate_has_correct_required_docs(self):
        """Inbox gate specifies common API doc formats."""
        parser = CommandParser()
        request = parser.parse("integrate courier DHL", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        gate = workspace.playbook.inbox_gates[0]
        assert "*.postman_collection.json" in gate.required_one_of
        assert "openapi.yaml" in gate.required_one_of
        assert "swagger.json" in gate.required_one_of

    def test_inbox_gate_requires_secrets_file(self):
        """Inbox gate requires secrets file by default."""
        parser = CommandParser()
        request = parser.parse("integrate courier UPS", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        gate = workspace.playbook.inbox_gates[0]
        assert gate.require_secrets_file is True

    def test_non_courier_integration_no_inbox_gate(self):
        """Non-courier integration has no inbox gate."""
        parser = CommandParser()
        # 'map api' intent should not have inbox gates
        request = parser.parse("map api PaymentGateway", include_timestamp=False)

        generator = WorkspaceGenerator()
        workspace = generator.generate(request)

        assert len(workspace.playbook.inbox_gates) == 0

    def test_inbox_gate_in_playbook_yaml(self):
        """Inbox gate appears in playbook.yaml output."""
        import yaml

        parser = CommandParser()
        request = parser.parse("integrate courier FedEx", include_timestamp=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceGenerator(Path(tmpdir))
            workspace = generator.generate(request)
            workspace_dir = generator.write_workspace(workspace)

            playbook_path = workspace_dir / "playbook.yaml"
            playbook_data = yaml.safe_load(playbook_path.read_text())

            assert "inbox_gates" in playbook_data
            assert len(playbook_data["inbox_gates"]) == 1
            assert playbook_data["inbox_gates"][0]["integration_id"] == "fedex"
