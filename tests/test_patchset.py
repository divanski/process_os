"""
ProcessOS Patchset Tests

Tests for Sprint 6: Patchset generation (output only).
"""

import pytest

from process_os.integrations.patchset import (
    Patchset,
    PatchEntry,
    PatchsetGenerator,
    generate_patchset,
)


class TestPatchsetSafety:
    """Test patchset safety guarantees."""

    def test_patchset_auto_apply_always_false(self):
        """auto_apply_allowed is always False."""
        patchset = Patchset(
            patchset_id="test",
            workspace_id="ws-test",
            target_description="Test",
        )

        assert patchset.auto_apply_allowed is False

    def test_patchset_auto_apply_cannot_be_enabled(self):
        """auto_apply_allowed cannot be set to True."""
        patchset = Patchset(
            patchset_id="test",
            workspace_id="ws-test",
            target_description="Test",
            auto_apply_allowed=True,  # Attempt to enable
        )

        # Should be forced to False by __post_init__
        assert patchset.auto_apply_allowed is False

    def test_patchset_requires_manual_review(self):
        """requires_manual_review is always True."""
        patchset = Patchset(
            patchset_id="test",
            workspace_id="ws-test",
            target_description="Test",
        )

        assert patchset.requires_manual_review is True


class TestPatchsetGeneration:
    """Test patchset generation."""

    def test_generate_modification_patch(self):
        """Can generate modification patch."""
        generator = PatchsetGenerator("ws-test")

        original = "line1\nline2\nline3\n"
        new = "line1\nmodified\nline3\n"

        patch = generator.add_modification(
            "src/test.py",
            original,
            new,
        )

        assert patch.operation == "modify"
        assert "modified" in patch.diff
        assert "-line2" in patch.diff
        assert "+modified" in patch.diff

    def test_generate_creation_patch(self):
        """Can generate creation patch."""
        generator = PatchsetGenerator("ws-test")

        content = "new file content\n"

        patch = generator.add_creation("src/new.py", content)

        assert patch.operation == "create"
        assert "+new file content" in patch.diff

    def test_generate_deletion_patch(self):
        """Can generate deletion patch."""
        generator = PatchsetGenerator("ws-test")

        original = "content to delete\n"

        patch = generator.add_deletion("src/old.py", original)

        assert patch.operation == "delete"
        assert "-content to delete" in patch.diff

    def test_patchset_output_only(self):
        """Generated patchset is output only."""
        generator = PatchsetGenerator("ws-test")
        generator.add_modification(
            "src/test.py",
            "old\n",
            "new\n",
        )

        patchset = generator.generate("Test change")

        # Safety checks enforced
        assert patchset.auto_apply_allowed is False
        assert patchset.requires_manual_review is True


class TestPatchsetDeterminism:
    """Test patchset determinism."""

    def test_patchset_id_deterministic(self):
        """Same inputs produce same patchset_id."""
        gen1 = PatchsetGenerator("ws-test")
        gen1.add_modification("src/test.py", "old\n", "new\n")
        ps1 = gen1.generate("Test change")

        gen2 = PatchsetGenerator("ws-test")
        gen2.add_modification("src/test.py", "old\n", "new\n")
        ps2 = gen2.generate("Test change")

        assert ps1.patchset_id == ps2.patchset_id

    def test_different_changes_different_ids(self):
        """Different changes produce different patchset_ids."""
        gen1 = PatchsetGenerator("ws-test")
        gen1.add_modification("src/test.py", "old\n", "new1\n")
        ps1 = gen1.generate("Change 1")

        gen2 = PatchsetGenerator("ws-test")
        gen2.add_modification("src/test.py", "old\n", "new2\n")
        ps2 = gen2.generate("Change 2")

        assert ps1.patchset_id != ps2.patchset_id


class TestPatchsetSerialization:
    """Test patchset serialization."""

    def test_patchset_to_dict(self):
        """Patchset can be serialized to dict."""
        generator = PatchsetGenerator("ws-test")
        generator.add_modification("src/test.py", "old\n", "new\n")
        patchset = generator.generate("Test")

        d = patchset.to_dict()

        assert "patchset_id" in d
        assert "workspace_id" in d
        assert "patches" in d
        assert "safety_checks" in d
        assert d["safety_checks"]["auto_apply_allowed"] is False

    def test_patchset_to_yaml(self):
        """Patchset can be serialized to YAML."""
        generator = PatchsetGenerator("ws-test")
        generator.add_modification("src/test.py", "old\n", "new\n")
        patchset = generator.generate("Test")

        yaml_str = patchset.to_yaml()

        assert "patchset_id:" in yaml_str
        assert "auto_apply_allowed: false" in yaml_str


class TestConvenienceFunction:
    """Test convenience function."""

    def test_generate_patchset_function(self):
        """generate_patchset convenience function works."""
        patchset = generate_patchset(
            workspace_id="ws-test",
            description="Add feature",
            modifications=[
                {
                    "file_path": "src/feature.py",
                    "original": "# old code\n",
                    "new": "# new code\n",
                }
            ],
        )

        assert patchset is not None
        assert len(patchset.patches) == 1
        assert patchset.auto_apply_allowed is False
