"""
ProcessOS Binding Tests

Tests for Sprint 7: Project binding.
"""

from pathlib import Path

import pytest

from process_os.init import (
    BindingGenerator,
    BindingManager,
    PROCESSOS_DIR,
    PROCESSOS_VERSION,
    ProjectBinding,
    generate_binding,
)
from process_os.stack_fingerprint import generate_fingerprint


class TestBindingGeneration:
    """Test binding generation."""

    def test_binding_created(self, tmp_path: Path):
        """Binding is created from fingerprint."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)

        assert binding is not None
        assert binding.binding_id.startswith("bind-")
        assert binding.fingerprint_ref == fp.fingerprint_id

    def test_binding_references_fingerprint(self, tmp_path: Path):
        """Binding correctly references fingerprint ID."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)

        assert binding.fingerprint_ref == fp.fingerprint_id

    def test_binding_idempotent(self, tmp_path: Path):
        """Same fingerprint produces same binding ID."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path, timestamp="2026-01-20T00:00:00Z")

        binding1 = generate_binding(fp, timestamp="2026-01-20T00:00:00Z")
        binding2 = generate_binding(fp, timestamp="2026-01-20T00:00:00Z")

        assert binding1.binding_id == binding2.binding_id

    def test_binding_schema(self, tmp_path: Path):
        """Binding to_dict has correct schema."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "myproject"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp, project_name="myproject")
        data = binding.to_dict()

        assert "binding_id" in data
        assert "created_at" in data
        assert "processos_version" in data
        assert "fingerprint_ref" in data
        assert "project" in data
        assert data["project"]["name"] == "myproject"
        assert "pillars" in data
        assert "rules_pack" in data

    def test_binding_version(self, tmp_path: Path):
        """Binding includes ProcessOS version."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)

        assert binding.processos_version == PROCESSOS_VERSION

    def test_binding_to_yaml(self, tmp_path: Path):
        """Binding serializes to YAML."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)
        yaml_str = binding.to_yaml()

        assert "binding_id:" in yaml_str
        assert "fingerprint_ref:" in yaml_str

    def test_binding_from_yaml(self, tmp_path: Path):
        """Binding deserializes from YAML."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding1 = generate_binding(fp)
        yaml_str = binding1.to_yaml()
        binding2 = ProjectBinding.from_yaml(yaml_str)

        assert binding2.binding_id == binding1.binding_id
        assert binding2.fingerprint_ref == binding1.fingerprint_ref

    def test_binding_with_pillars(self, tmp_path: Path):
        """Binding can include active pillars."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp, pillars=["courier"])

        assert "courier" in binding.pillars


class TestBindingManager:
    """Test binding manager."""

    def test_manager_creates_directory(self, tmp_path: Path):
        """Manager creates .processos directory."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        manager = BindingManager(tmp_path)
        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)

        manager.save_binding(binding)

        assert (tmp_path / PROCESSOS_DIR).exists()
        assert (tmp_path / PROCESSOS_DIR / "binding.yaml").exists()

    def test_manager_exists_check(self, tmp_path: Path):
        """Manager correctly checks if binding exists."""
        manager = BindingManager(tmp_path)

        assert manager.exists() is False

        (tmp_path / PROCESSOS_DIR).mkdir()
        (tmp_path / PROCESSOS_DIR / "binding.yaml").write_text("binding_id: test\n")

        assert manager.exists() is True

    def test_manager_loads_binding(self, tmp_path: Path):
        """Manager loads saved binding."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        manager = BindingManager(tmp_path)
        fp = generate_fingerprint(tmp_path)
        binding = generate_binding(fp)

        manager.save_binding(binding)
        loaded = manager.load_binding()

        assert loaded.binding_id == binding.binding_id

    def test_manager_saves_fingerprint(self, tmp_path: Path):
        """Manager saves fingerprint file."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        manager = BindingManager(tmp_path)
        fp = generate_fingerprint(tmp_path)

        manager.save_fingerprint(fp)

        assert (tmp_path / PROCESSOS_DIR / "fingerprint.yaml").exists()

    def test_manager_loads_fingerprint(self, tmp_path: Path):
        """Manager loads saved fingerprint."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        manager = BindingManager(tmp_path)
        fp = generate_fingerprint(tmp_path)

        manager.save_fingerprint(fp)
        loaded = manager.load_fingerprint()

        assert loaded.fingerprint_id == fp.fingerprint_id
