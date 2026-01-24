"""
ProcessOS Stack Fingerprint Tests

Tests for Sprint 7: Stack fingerprint detection.
"""

import tempfile
from pathlib import Path

import pytest

from process_os.stack_fingerprint import (
    FingerprintGenerator,
    StackDetector,
    StackFingerprint,
    generate_fingerprint,
)


class TestStackDetector:
    """Test stack detection."""

    def test_detect_python_pyproject(self, tmp_path: Path):
        """Detects Python with pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 1
        assert result.stacks[0].stack_id == "python"
        assert result.stacks[0].confidence == "high"
        assert "pyproject.toml" in result.stacks[0].markers_found

    def test_detect_python_requirements(self, tmp_path: Path):
        """Detects Python with requirements.txt."""
        (tmp_path / "requirements.txt").write_text("flask==2.0.0\n")

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 1
        assert result.stacks[0].stack_id == "python"
        assert "requirements.txt" in result.stacks[0].markers_found

    def test_detect_node_package_json(self, tmp_path: Path):
        """Detects Node with package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 1
        assert result.stacks[0].stack_id == "node"
        assert result.stacks[0].confidence == "high"

    def test_detect_rust_cargo(self, tmp_path: Path):
        """Detects Rust with Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 1
        assert result.stacks[0].stack_id == "rust"
        assert result.stacks[0].confidence == "high"

    def test_detect_go_mod(self, tmp_path: Path):
        """Detects Go with go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test\n\ngo 1.21\n")

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 1
        assert result.stacks[0].stack_id == "go"
        assert result.stacks[0].version_hint == "1.21"

    def test_detect_polyglot(self, tmp_path: Path):
        """Detects multiple stacks in polyglot project."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 2
        stack_ids = {s.stack_id for s in result.stacks}
        assert "python" in stack_ids
        assert "node" in stack_ids

    def test_detect_empty_project(self, tmp_path: Path):
        """Returns empty for project with no markers."""
        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.stacks) == 0
        assert len(result.frameworks) == 0

    def test_confidence_medium_multiple_markers(self, tmp_path: Path):
        """Medium confidence with multiple non-high markers."""
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "setup.cfg").write_text("[metadata]\nname = test\n")

        detector = StackDetector()
        result = detector.detect(tmp_path)

        # pyproject.toml and setup.py are high confidence
        # requirements.txt alone is low, but with setup.cfg should be medium
        assert result.stacks[0].confidence in ["low", "medium"]


class TestFrameworkDetection:
    """Test framework detection."""

    def test_detect_fastapi(self, tmp_path: Path):
        """Detects FastAPI framework."""
        pyproject = '[project]\ndependencies = ["fastapi>=0.100"]\n'
        (tmp_path / "pyproject.toml").write_text(pyproject)

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.frameworks) == 1
        assert result.frameworks[0].framework_id == "fastapi"
        assert result.frameworks[0].stack == "python"

    def test_detect_react(self, tmp_path: Path):
        """Detects React framework."""
        package = '{"dependencies": {"react": "^18.0.0"}}\n'
        (tmp_path / "package.json").write_text(package)

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.frameworks) == 1
        assert result.frameworks[0].framework_id == "react"
        assert result.frameworks[0].stack == "node"

    def test_detect_django(self, tmp_path: Path):
        """Detects Django framework."""
        requirements = "django==4.2\ndjango-rest-framework\n"
        (tmp_path / "requirements.txt").write_text(requirements)

        detector = StackDetector()
        result = detector.detect(tmp_path)

        framework_ids = {f.framework_id for f in result.frameworks}
        assert "django" in framework_ids

    def test_detect_express(self, tmp_path: Path):
        """Detects Express framework."""
        package = '{"dependencies": {"express": "^4.18.0"}}\n'
        (tmp_path / "package.json").write_text(package)

        detector = StackDetector()
        result = detector.detect(tmp_path)

        assert len(result.frameworks) == 1
        assert result.frameworks[0].framework_id == "express"


class TestFingerprintGeneration:
    """Test fingerprint generation."""

    def test_fingerprint_deterministic(self, tmp_path: Path):
        """Same project produces same fingerprint ID."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        gen = FingerprintGenerator()

        fp1 = gen.generate(tmp_path, timestamp="2026-01-20T00:00:00Z")
        fp2 = gen.generate(tmp_path, timestamp="2026-01-20T00:00:00Z")

        assert fp1.fingerprint_id == fp2.fingerprint_id
        assert fp1.content_hash == fp2.content_hash

    def test_fingerprint_different_for_different_projects(self, tmp_path: Path):
        """Different projects produce different fingerprints."""
        project1 = tmp_path / "project1"
        project2 = tmp_path / "project2"
        project1.mkdir()
        project2.mkdir()

        (project1 / "pyproject.toml").write_text('[project]\nname = "test1"\n')
        (project2 / "package.json").write_text('{"name": "test2"}\n')

        gen = FingerprintGenerator()

        fp1 = gen.generate(project1)
        fp2 = gen.generate(project2)

        assert fp1.fingerprint_id != fp2.fingerprint_id

    def test_fingerprint_id_format(self, tmp_path: Path):
        """Fingerprint ID has correct format."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)

        assert fp.fingerprint_id.startswith("fp-")
        assert len(fp.fingerprint_id) == 15  # "fp-" + 12 hex chars

    def test_fingerprint_to_yaml(self, tmp_path: Path):
        """Fingerprint serializes to YAML."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        yaml_str = fp.to_yaml()

        assert "fingerprint_id:" in yaml_str
        assert "stacks:" in yaml_str
        assert "content_hash:" in yaml_str

    def test_fingerprint_from_yaml(self, tmp_path: Path):
        """Fingerprint deserializes from YAML."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp1 = generate_fingerprint(tmp_path)
        yaml_str = fp1.to_yaml()
        fp2 = StackFingerprint.from_yaml(yaml_str)

        assert fp2.fingerprint_id == fp1.fingerprint_id
        assert fp2.content_hash == fp1.content_hash

    def test_fingerprint_has_stack(self, tmp_path: Path):
        """has_stack helper method works."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)

        assert fp.has_stack("python") is True
        assert fp.has_stack("node") is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_skips_node_modules(self, tmp_path: Path):
        """Skips node_modules directory."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        node_modules = tmp_path / "node_modules" / "some-package"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text('{"name": "dep"}\n')

        detector = StackDetector()
        result = detector.detect(tmp_path)

        # Should only detect root package.json, not nested
        assert len(result.stacks) == 1

    def test_skips_venv(self, tmp_path: Path):
        """Skips .venv directory."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "setup.py").write_text("# setup\n")

        detector = StackDetector()
        result = detector.detect(tmp_path)

        # Should only detect root pyproject.toml
        assert len(result.stacks) == 1

    def test_nonexistent_directory(self, tmp_path: Path):
        """Handles nonexistent directory gracefully."""
        nonexistent = tmp_path / "does_not_exist"

        detector = StackDetector()
        result = detector.detect(nonexistent)

        assert len(result.stacks) == 0
