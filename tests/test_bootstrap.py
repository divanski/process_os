"""
ProcessOS Bootstrap Tests

Tests for Sprint 8: Bootstrap command and instruction pack.
"""

import json
from pathlib import Path

import pytest

from process_os.bootstrap import (
    Bootstrapper,
    BootstrapResult,
    bootstrap_host,
    InstructionPackConfig,
    InstructionPackGenerator,
)
from process_os.stack_fingerprint import generate_fingerprint


class TestBootstrapper:
    """Test bootstrapper."""

    def test_bootstrap_creates_processos_dir(self, tmp_path: Path):
        """Bootstrap creates .processos directory."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        bootstrapper = Bootstrapper(tmp_path)
        output = bootstrapper.bootstrap()

        assert output.result == BootstrapResult.SUCCESS
        assert (tmp_path / ".processos").exists()

    def test_bootstrap_creates_binding(self, tmp_path: Path):
        """Bootstrap creates binding.yaml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        assert (tmp_path / ".processos" / "binding.yaml").exists()
        assert output.binding_id.startswith("bind-")

    def test_bootstrap_creates_fingerprint(self, tmp_path: Path):
        """Bootstrap creates fingerprint.yaml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        assert (tmp_path / ".processos" / "fingerprint.yaml").exists()
        assert output.fingerprint_id.startswith("fp-")

    def test_bootstrap_creates_claude_pack(self, tmp_path: Path):
        """Bootstrap creates Claude instruction pack."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        claude_dir = tmp_path / ".processos" / "claude"
        assert claude_dir.exists()
        assert (claude_dir / "INSTRUCTIONS.md").exists()
        assert (claude_dir / "CONTRACTS.md").exists()
        assert (claude_dir / "ENTRYPOINT_PROMPT.txt").exists()
        assert (claude_dir / "PROJECT_CONTEXT.json").exists()

    def test_bootstrap_idempotent(self, tmp_path: Path):
        """Same bootstrap twice produces same IDs."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output1 = bootstrap_host(tmp_path, timestamp="2026-01-20T00:00:00Z")

        # Force re-bootstrap with same timestamp
        output2 = bootstrap_host(tmp_path, force=True, timestamp="2026-01-20T00:00:00Z")

        assert output1.binding_id == output2.binding_id
        assert output1.fingerprint_id == output2.fingerprint_id

    def test_bootstrap_already_exists(self, tmp_path: Path):
        """Bootstrap returns error if already bootstrapped."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        bootstrap_host(tmp_path)
        output = bootstrap_host(tmp_path)

        assert output.result == BootstrapResult.ALREADY_BOOTSTRAPPED

    def test_bootstrap_force_overwrites(self, tmp_path: Path):
        """Bootstrap with force overwrites existing."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        bootstrap_host(tmp_path)
        output = bootstrap_host(tmp_path, force=True)

        assert output.result == BootstrapResult.SUCCESS

    def test_bootstrap_invalid_host(self, tmp_path: Path):
        """Bootstrap returns error for invalid host path."""
        nonexistent = tmp_path / "does_not_exist"

        output = bootstrap_host(nonexistent)

        assert output.result == BootstrapResult.INVALID_HOST

    def test_is_bootstrapped(self, tmp_path: Path):
        """is_bootstrapped returns correct state."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        bootstrapper = Bootstrapper(tmp_path)

        assert bootstrapper.is_bootstrapped() is False

        bootstrapper.bootstrap()

        assert bootstrapper.is_bootstrapped() is True


class TestInstructionPack:
    """Test instruction pack generation."""

    def test_pack_deterministic(self, tmp_path: Path):
        """Same config produces identical pack files."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path, timestamp="2026-01-20T00:00:00Z")

        config = InstructionPackConfig(
            project_name="test",
            host_root=tmp_path,
            fingerprint=fp,
            binding_id="bind-test123",
        )

        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"

        gen1 = InstructionPackGenerator(config)
        gen1.set_timestamp("2026-01-20T00:00:00Z")
        gen1.generate(out1)

        gen2 = InstructionPackGenerator(config)
        gen2.set_timestamp("2026-01-20T00:00:00Z")
        gen2.generate(out2)

        # Compare all files
        for fname in ["INSTRUCTIONS.md", "CONTRACTS.md", "ENTRYPOINT_PROMPT.txt", "PROJECT_CONTEXT.json"]:
            content1 = (out1 / fname).read_text()
            content2 = (out2 / fname).read_text()
            assert content1 == content2, f"{fname} differs"

    def test_instructions_contains_rules(self, tmp_path: Path):
        """INSTRUCTIONS.md contains key rules."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        instructions = (tmp_path / ".processos" / "claude" / "INSTRUCTIONS.md").read_text()

        assert "NEVER" in instructions
        assert ".processos" in instructions
        assert "processos cmd" in instructions

    def test_contracts_contains_policies(self, tmp_path: Path):
        """CONTRACTS.md contains policy information."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        bootstrap_host(tmp_path)

        contracts = (tmp_path / ".processos" / "claude" / "CONTRACTS.md").read_text()

        assert "Write Allowlist" in contracts
        assert "Forbidden Actions" in contracts
        assert "HALT" in contracts

    def test_entrypoint_copyable(self, tmp_path: Path):
        """ENTRYPOINT_PROMPT.txt is ready for copy-paste."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        entrypoint = (tmp_path / ".processos" / "claude" / "ENTRYPOINT_PROMPT.txt").read_text()

        assert "Claude" in entrypoint
        assert output.fingerprint_id in entrypoint
        assert "processos cmd" in entrypoint

    def test_context_json_valid(self, tmp_path: Path):
        """PROJECT_CONTEXT.json is valid JSON with required fields."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = bootstrap_host(tmp_path)

        context_path = tmp_path / ".processos" / "claude" / "PROJECT_CONTEXT.json"
        context = json.loads(context_path.read_text())

        assert context["fingerprint_id"] == output.fingerprint_id
        assert context["binding_id"] == output.binding_id
        assert "stacks" in context
        assert "policies" in context
        assert context["policies"]["tools_enabled"] is False
        assert context["policies"]["auto_apply_patchsets"] is False


class TestFixtureHosts:
    """Test with fixture host projects."""

    @pytest.fixture
    def laravel_fixture(self) -> Path:
        """Get Laravel-like fixture path."""
        return Path(__file__).parent / "fixtures" / "fixture_hosts" / "laravel_like"

    @pytest.fixture
    def react_fixture(self) -> Path:
        """Get React-like fixture path."""
        return Path(__file__).parent / "fixtures" / "fixture_hosts" / "react_like"

    @pytest.fixture
    def empty_fixture(self) -> Path:
        """Get empty fixture path."""
        return Path(__file__).parent / "fixtures" / "fixture_hosts" / "empty_project"

    def test_bootstrap_laravel_detects_php(self, laravel_fixture: Path, tmp_path: Path):
        """Bootstrap detects PHP in Laravel-like project."""
        # Copy fixture to tmp for isolation
        import shutil
        test_dir = tmp_path / "laravel"
        shutil.copytree(laravel_fixture, test_dir)

        output = bootstrap_host(test_dir)

        assert output.result == BootstrapResult.SUCCESS

        context = json.loads((test_dir / ".processos" / "claude" / "PROJECT_CONTEXT.json").read_text())
        stack_ids = [s["stack_id"] for s in context["stacks"]]
        assert "php" in stack_ids

    def test_bootstrap_react_detects_node(self, react_fixture: Path, tmp_path: Path):
        """Bootstrap detects Node in React-like project."""
        import shutil
        test_dir = tmp_path / "react"
        shutil.copytree(react_fixture, test_dir)

        output = bootstrap_host(test_dir)

        assert output.result == BootstrapResult.SUCCESS

        context = json.loads((test_dir / ".processos" / "claude" / "PROJECT_CONTEXT.json").read_text())
        stack_ids = [s["stack_id"] for s in context["stacks"]]
        assert "node" in stack_ids

    def test_bootstrap_empty_no_stacks(self, empty_fixture: Path, tmp_path: Path):
        """Bootstrap handles empty project with no stacks."""
        import shutil
        test_dir = tmp_path / "empty"
        shutil.copytree(empty_fixture, test_dir)

        output = bootstrap_host(test_dir)

        assert output.result == BootstrapResult.SUCCESS

        context = json.loads((test_dir / ".processos" / "claude" / "PROJECT_CONTEXT.json").read_text())
        assert context["stacks"] == []
