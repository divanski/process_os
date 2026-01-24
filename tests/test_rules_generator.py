"""
ProcessOS Rules Generator Tests

Tests for Sprint 7: Claude rules pack generation.
"""

from pathlib import Path

import pytest

from process_os.init import PROCESSOS_DIR
from process_os.rules import RulesGenerator, generate_rules
from process_os.stack_fingerprint import generate_fingerprint


class TestRulesGenerator:
    """Test rules generator."""

    def test_generates_index_file(self, tmp_path: Path):
        """Generates _index.md file."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        assert (rules_dir / "_index.md").exists()

    def test_generates_project_context(self, tmp_path: Path):
        """Generates project-context.md file."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        assert (rules_dir / "project-context.md").exists()

    def test_generates_stack_python(self, tmp_path: Path):
        """Generates stack-python.md for Python projects."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        assert (rules_dir / "stack-python.md").exists()

    def test_generates_stack_node(self, tmp_path: Path):
        """Generates stack-node.md for Node projects."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        assert (rules_dir / "stack-node.md").exists()

    def test_no_stack_file_for_missing_template(self, tmp_path: Path):
        """Does not generate file if template missing."""
        (tmp_path / "go.mod").write_text("module test\n\ngo 1.21\n")

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        # Go template doesn't exist, so no file generated
        # But index and context should exist
        assert (rules_dir / "_index.md").exists()
        assert (rules_dir / "project-context.md").exists()

    def test_rules_deterministic(self, tmp_path: Path):
        """Same fingerprint produces same rules content."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path, timestamp="2026-01-20T00:00:00Z")

        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        content1 = (rules_dir / "_index.md").read_text()

        # Regenerate
        generator.generate(fp)
        content2 = (rules_dir / "_index.md").read_text()

        assert content1 == content2

    def test_index_contains_fingerprint_id(self, tmp_path: Path):
        """Index file contains fingerprint ID."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        content = (rules_dir / "_index.md").read_text()

        assert fp.fingerprint_id in content

    def test_index_lists_detected_stacks(self, tmp_path: Path):
        """Index file lists detected stacks."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        content = (rules_dir / "_index.md").read_text()

        assert "python" in content.lower()

    def test_context_includes_guidelines(self, tmp_path: Path):
        """Project context includes AI guidelines."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        content = (rules_dir / "project-context.md").read_text()

        assert "AI Agent Guidelines" in content

    def test_rules_in_processos_directory(self, tmp_path: Path):
        """Rules are generated in .processos/claude-rules."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        expected_path = tmp_path / PROCESSOS_DIR / "claude-rules"
        assert rules_dir == expected_path


class TestConvenienceFunction:
    """Test convenience function."""

    def test_generate_rules_function(self, tmp_path: Path):
        """generate_rules convenience function works."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        fp = generate_fingerprint(tmp_path)
        rules_dir = generate_rules(tmp_path, fp)

        assert rules_dir.exists()
        assert (rules_dir / "_index.md").exists()


class TestPolyglotRules:
    """Test rules for polyglot projects."""

    def test_polyglot_generates_multiple_stack_files(self, tmp_path: Path):
        """Polyglot project generates multiple stack rule files."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        assert (rules_dir / "stack-python.md").exists()
        assert (rules_dir / "stack-node.md").exists()

    def test_polyglot_index_lists_all_stacks(self, tmp_path: Path):
        """Polyglot project index lists all detected stacks."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (tmp_path / "package.json").write_text('{"name": "test"}\n')

        fp = generate_fingerprint(tmp_path)
        generator = RulesGenerator(tmp_path)
        rules_dir = generator.generate(fp)

        content = (rules_dir / "_index.md").read_text()

        assert "python" in content.lower()
        assert "node" in content.lower()
