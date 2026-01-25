"""
ProcessOS CLI Tests

Tests for Sprint 7: CLI commands.
"""

from pathlib import Path

import pytest

from process_os.cli import create_parser, main
from process_os.init import PROCESSOS_DIR


class TestCLIParser:
    """Test CLI argument parser."""

    def test_parser_creates(self):
        """Parser is created successfully."""
        parser = create_parser()
        assert parser is not None

    def test_parser_has_init_command(self):
        """Parser has init subcommand."""
        parser = create_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"

    def test_parser_has_status_command(self):
        """Parser has status subcommand."""
        parser = create_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_parser_has_fingerprint_command(self):
        """Parser has fingerprint subcommand."""
        parser = create_parser()
        args = parser.parse_args(["fingerprint"])
        assert args.command == "fingerprint"

    def test_init_accepts_project_root(self):
        """Init command accepts --project-root."""
        parser = create_parser()
        args = parser.parse_args(["init", "--project-root", "/tmp/test"])
        assert args.project_root == "/tmp/test"

    def test_init_accepts_force(self):
        """Init command accepts --force."""
        parser = create_parser()
        args = parser.parse_args(["init", "--force"])
        assert args.force is True

    def test_init_accepts_name(self):
        """Init command accepts --name."""
        parser = create_parser()
        args = parser.parse_args(["init", "--name", "myproject"])
        assert args.name == "myproject"

    def test_no_command_returns_zero(self):
        """No command prints help and returns 0."""
        result = main([])
        assert result == 0


class TestCLIInit:
    """Test CLI init command."""

    def test_init_command(self, tmp_path: Path):
        """Init command creates binding."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        result = main(["init", "--project-root", str(tmp_path)])

        assert result == 0
        assert (tmp_path / PROCESSOS_DIR / "config.yaml").exists()

    def test_init_creates_rules(self, tmp_path: Path):
        """Init command creates rules pack."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        result = main(["init", "--project-root", str(tmp_path)])

        assert result == 0
        assert (tmp_path / PROCESSOS_DIR / "claude").exists()

    def test_init_already_exists(self, tmp_path: Path):
        """Init returns 1 if already initialized."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        main(["init", "--project-root", str(tmp_path)])
        result = main(["init", "--project-root", str(tmp_path)])

        assert result == 1

    def test_init_force(self, tmp_path: Path):
        """Init with --force reinitializes."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        main(["init", "--project-root", str(tmp_path)])
        result = main(["init", "--project-root", str(tmp_path), "--force"])

        assert result == 0

    def test_init_with_name(self, tmp_path: Path):
        """Init with --name sets project name."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        result = main(["init", "--project-root", str(tmp_path), "--name", "custom"])

        assert result == 0

    def test_init_nonexistent_path(self, tmp_path: Path):
        """Init with nonexistent path returns error."""
        nonexistent = tmp_path / "does_not_exist"

        result = main(["init", "--project-root", str(nonexistent)])

        assert result == 2  # Detection failed


class TestCLIStatus:
    """Test CLI status command."""

    def test_status_uninitialized(self, tmp_path: Path):
        """Status for uninitialized project returns 1."""
        result = main(["status", "--project-root", str(tmp_path)])

        assert result == 1

    def test_status_initialized(self, tmp_path: Path):
        """Status for initialized project returns 0."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        main(["init", "--project-root", str(tmp_path)])
        result = main(["status", "--project-root", str(tmp_path)])

        assert result == 0


class TestCLIFingerprint:
    """Test CLI fingerprint command."""

    def test_fingerprint_uninitialized(self, tmp_path: Path):
        """Fingerprint for uninitialized project fails."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        result = main(["fingerprint", "--project-root", str(tmp_path)])

        assert result != 0

    def test_fingerprint_refreshes(self, tmp_path: Path):
        """Fingerprint command refreshes detection."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        main(["init", "--project-root", str(tmp_path)])
        result = main(["fingerprint", "--project-root", str(tmp_path)])

        assert result == 0
