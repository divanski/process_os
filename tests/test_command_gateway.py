"""
ProcessOS Command Gateway Tests

Tests for Sprint 8: Command gateway execution.
"""

from pathlib import Path

import pytest
import yaml

from process_os.bootstrap import (
    bootstrap_host,
    CommandGateway,
    execute_command,
)


class TestCommandGateway:
    """Test command gateway."""

    def test_gateway_requires_bootstrap(self, tmp_path: Path):
        """Gateway requires bootstrapped host."""
        gateway = CommandGateway(tmp_path)
        result = gateway.execute("test command")

        assert result.success is False
        assert "not initialized" in result.error.lower()

    def test_gateway_produces_command_id(self, tmp_path: Path):
        """Gateway produces deterministic command_id."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        gateway = CommandGateway(tmp_path)
        result = gateway.execute("integrate courier DHL")

        assert result.command_id.startswith("cmd-")
        assert len(result.command_id) > 10

    def test_gateway_produces_workspace_id(self, tmp_path: Path):
        """Gateway produces workspace_id."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "integrate courier DHL")

        assert result.workspace_id.startswith("ws-")

    def test_gateway_produces_run_id(self, tmp_path: Path):
        """Gateway produces run_id."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "integrate courier DHL")

        assert len(result.run_id) > 0

    def test_gateway_deterministic_ids(self, tmp_path: Path):
        """Same command produces same command_id."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result1 = execute_command(tmp_path, "integrate courier DHL")
        result2 = execute_command(tmp_path, "integrate courier DHL")

        assert result1.command_id == result2.command_id

    def test_gateway_creates_run_dir(self, tmp_path: Path):
        """Gateway creates run directory."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "integrate courier DHL")

        assert result.run_dir is not None
        assert result.run_dir.exists()

    def test_gateway_writes_trace_summary(self, tmp_path: Path):
        """Gateway writes trace.yaml with chain."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "integrate courier DHL")

        trace_file = result.run_dir / "trace.yaml"
        assert trace_file.exists()

        trace = yaml.safe_load(trace_file.read_text())
        assert trace["trace_chain"]["command_id"] == result.command_id
        assert trace["trace_chain"]["workspace_id"] == result.workspace_id
        assert trace["trace_chain"]["run_id"] == result.run_id


class TestTraceChainIntegrity:
    """Test trace chain integrity (INV-05)."""

    def test_trace_chain_consistent(self, tmp_path: Path):
        """command_id → workspace_id → run_id chain is consistent."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "integrate courier DHL")

        # Read trace file
        trace = yaml.safe_load((result.run_dir / "trace.yaml").read_text())

        # Verify chain
        assert trace["trace_chain"]["command_id"] == result.command_id
        assert trace["trace_chain"]["workspace_id"] == result.workspace_id
        assert trace["trace_chain"]["run_id"] == result.run_id

        # Verify workspace_id derived from command_id
        assert result.workspace_id.endswith(result.command_id.replace("cmd-", ""))

    def test_trace_contains_binding_ref(self, tmp_path: Path):
        """Trace contains binding and fingerprint references."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        output = bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "test task")

        trace = yaml.safe_load((result.run_dir / "trace.yaml").read_text())

        assert trace["binding_id"] == output.binding_id
        assert trace["fingerprint_id"] == output.fingerprint_id


class TestWriteAllowlistEnforcement:
    """Test that gateway only writes to .processos/ (INV-03)."""

    def test_runs_in_processos_dir(self, tmp_path: Path):
        """All runs are in .processos/runs/."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        result = execute_command(tmp_path, "test task")

        # Run dir should be under .processos/runs/
        assert ".processos" in str(result.run_dir)
        assert "runs" in str(result.run_dir)

    def test_workspaces_in_processos_dir(self, tmp_path: Path):
        """All workspaces are in .processos/workspaces/."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)

        execute_command(tmp_path, "test task")

        workspaces_dir = tmp_path / ".processos" / "workspaces"
        assert workspaces_dir.exists()


class TestNoHiddenState:
    """Test no hidden state (INV-06)."""

    def test_all_state_in_processos(self, tmp_path: Path):
        """All generated state is in .processos/."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        bootstrap_host(tmp_path)
        execute_command(tmp_path, "test task")

        # Count files in tmp_path (excluding .processos)
        other_files = []
        for f in tmp_path.rglob("*"):
            if ".processos" not in str(f) and f.is_file():
                if f.name != "pyproject.toml":
                    other_files.append(f)

        # Should only have pyproject.toml outside .processos
        assert len(other_files) == 0, f"Unexpected files: {other_files}"
