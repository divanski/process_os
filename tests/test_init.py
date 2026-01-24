"""
ProcessOS Init Tests

Tests for Sprint 7: Project initialization.
"""

from pathlib import Path

import pytest

from process_os.init import (
    InitResult,
    PROCESSOS_DIR,
    ProjectInitializer,
    init_project,
)


class TestProjectInitializer:
    """Test project initializer."""

    def test_init_creates_directory(self, tmp_path: Path):
        """Init creates .processos directory."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init()

        assert output.result == InitResult.SUCCESS
        assert (tmp_path / PROCESSOS_DIR).exists()

    def test_init_writes_fingerprint(self, tmp_path: Path):
        """Init creates fingerprint.yaml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init()

        assert (tmp_path / PROCESSOS_DIR / "fingerprint.yaml").exists()
        assert output.fingerprint is not None

    def test_init_writes_binding(self, tmp_path: Path):
        """Init creates binding.yaml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init()

        assert (tmp_path / PROCESSOS_DIR / "binding.yaml").exists()
        assert output.binding is not None

    def test_init_returns_rules_dir(self, tmp_path: Path):
        """Init returns rules directory path."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init()

        assert output.rules_dir is not None
        assert str(output.rules_dir).endswith("claude-rules")

    def test_init_exit_code_success(self, tmp_path: Path):
        """Init returns SUCCESS for new project."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init()

        assert output.result == InitResult.SUCCESS
        assert output.result.value == 0

    def test_init_exit_code_exists(self, tmp_path: Path):
        """Init returns ALREADY_EXISTS for initialized project."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        initializer.init()

        # Second init without force
        output = initializer.init()

        assert output.result == InitResult.ALREADY_EXISTS
        assert output.result.value == 1

    def test_init_force_overwrites(self, tmp_path: Path):
        """Init with force overwrites existing binding."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output1 = initializer.init()

        # Second init with force
        output2 = initializer.init(force=True)

        assert output2.result == InitResult.SUCCESS
        assert output2.binding is not None

    def test_init_with_project_name(self, tmp_path: Path):
        """Init uses provided project name."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init(project_name="my-custom-name")

        assert output.binding.project_name == "my-custom-name"

    def test_init_with_pillars(self, tmp_path: Path):
        """Init includes specified pillars."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        output = initializer.init(pillars=["courier"])

        assert "courier" in output.binding.pillars


class TestInitStatus:
    """Test status command."""

    def test_status_uninitialized(self, tmp_path: Path):
        """Status returns error for uninitialized project."""
        initializer = ProjectInitializer(tmp_path)
        output = initializer.status()

        assert output.result != InitResult.SUCCESS
        assert "not initialized" in output.message.lower()

    def test_status_initialized(self, tmp_path: Path):
        """Status returns success for initialized project."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        initializer.init()

        output = initializer.status()

        assert output.result == InitResult.SUCCESS
        assert output.binding is not None
        assert output.fingerprint is not None


class TestRefreshFingerprint:
    """Test fingerprint refresh."""

    def test_refresh_updates_fingerprint(self, tmp_path: Path):
        """Refresh updates fingerprint file."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        initializer = ProjectInitializer(tmp_path)
        initializer.init()

        output = initializer.refresh_fingerprint()

        assert output.result == InitResult.SUCCESS
        assert output.fingerprint is not None

    def test_refresh_uninitialized_fails(self, tmp_path: Path):
        """Refresh fails for uninitialized project."""
        initializer = ProjectInitializer(tmp_path)
        output = initializer.refresh_fingerprint()

        assert output.result != InitResult.SUCCESS


class TestConvenienceFunction:
    """Test convenience function."""

    def test_init_project_function(self, tmp_path: Path):
        """init_project convenience function works."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        output = init_project(tmp_path)

        assert output.result == InitResult.SUCCESS
        assert output.binding is not None
        assert output.fingerprint is not None
