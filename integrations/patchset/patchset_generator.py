"""
ProcessOS Patchset Generator

Generates unified diff patches for proposed code changes.

CRITICAL: Patches are OUTPUT ONLY. They are NEVER auto-applied.
Patches must be reviewed and applied manually by humans.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PatchEntry:
    """
    Single patch entry for a file modification.

    Contains the unified diff and metadata.
    """

    file_path: str
    operation: str  # "create", "modify", "delete"
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff: str = ""

    # Safety checks
    syntax_valid: Optional[bool] = None
    imports_resolvable: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "file_path": self.file_path,
            "operation": self.operation,
            "diff": self.diff,
        }
        if self.syntax_valid is not None:
            result["syntax_valid"] = self.syntax_valid
        if self.imports_resolvable is not None:
            result["imports_resolvable"] = self.imports_resolvable
        return result


@dataclass
class Patchset:
    """
    Collection of patches for a proposed change.

    SAFETY: auto_apply_allowed is ALWAYS False.
    """

    patchset_id: str
    workspace_id: str
    target_description: str
    patches: List[PatchEntry] = field(default_factory=list)
    created_at: str = ""

    # Safety checks - ALWAYS safe by design
    has_destructive_changes: bool = False
    requires_manual_review: bool = True
    auto_apply_allowed: bool = False  # ALWAYS False

    def __post_init__(self):
        """Enforce safety invariants."""
        # CRITICAL: auto_apply_allowed must ALWAYS be False
        self.auto_apply_allowed = False
        self.requires_manual_review = True

        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "patchset_id": self.patchset_id,
            "workspace_id": self.workspace_id,
            "target_description": self.target_description,
            "created_at": self.created_at,
            "patches": [p.to_dict() for p in self.patches],
            "safety_checks": {
                "has_destructive_changes": self.has_destructive_changes,
                "requires_manual_review": self.requires_manual_review,
                "auto_apply_allowed": self.auto_apply_allowed,  # Always False
            },
        }

    def to_yaml(self) -> str:
        """Serialize to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=True)


class PatchsetGenerator:
    """
    Generates patchsets for proposed code changes.

    SAFETY: This class ONLY generates patches. It does NOT apply them.
    """

    def __init__(self, workspace_id: str):
        """
        Initialize patchset generator.

        Args:
            workspace_id: Associated workspace ID
        """
        self.workspace_id = workspace_id
        self._patches: List[PatchEntry] = []

    def add_modification(
        self,
        file_path: str,
        original_content: str,
        new_content: str,
    ) -> PatchEntry:
        """
        Add a file modification patch.

        Args:
            file_path: Path to file being modified
            original_content: Original file content
            new_content: Proposed new content

        Returns:
            Generated PatchEntry
        """
        # Generate unified diff
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))

        diff = "".join(diff_lines)

        patch = PatchEntry(
            file_path=file_path,
            operation="modify",
            original_content=original_content,
            new_content=new_content,
            diff=diff,
        )

        self._patches.append(patch)
        return patch

    def add_creation(
        self,
        file_path: str,
        content: str,
    ) -> PatchEntry:
        """
        Add a file creation patch.

        Args:
            file_path: Path for new file
            content: File content

        Returns:
            Generated PatchEntry
        """
        # Generate diff for new file
        new_lines = content.splitlines(keepends=True)

        diff_lines = list(unified_diff(
            [],
            new_lines,
            fromfile="/dev/null",
            tofile=f"b/{file_path}",
        ))

        diff = "".join(diff_lines)

        patch = PatchEntry(
            file_path=file_path,
            operation="create",
            new_content=content,
            diff=diff,
        )

        self._patches.append(patch)
        return patch

    def add_deletion(
        self,
        file_path: str,
        original_content: str,
    ) -> PatchEntry:
        """
        Add a file deletion patch.

        Args:
            file_path: Path to file being deleted
            original_content: Current file content

        Returns:
            Generated PatchEntry
        """
        # Generate diff for deletion
        original_lines = original_content.splitlines(keepends=True)

        diff_lines = list(unified_diff(
            original_lines,
            [],
            fromfile=f"a/{file_path}",
            tofile="/dev/null",
        ))

        diff = "".join(diff_lines)

        patch = PatchEntry(
            file_path=file_path,
            operation="delete",
            original_content=original_content,
            diff=diff,
        )

        self._patches.append(patch)
        return patch

    def generate(self, description: str) -> Patchset:
        """
        Generate final patchset.

        Args:
            description: Description of the changes

        Returns:
            Complete Patchset (output only, never auto-applied)
        """
        # Generate deterministic patchset ID
        content_hash = hashlib.sha256()
        content_hash.update(self.workspace_id.encode())
        content_hash.update(description.encode())
        for patch in self._patches:
            content_hash.update(patch.diff.encode())

        patchset_id = f"patch-{content_hash.hexdigest()[:12]}"

        # Check for destructive changes
        has_destructive = any(p.operation == "delete" for p in self._patches)

        return Patchset(
            patchset_id=patchset_id,
            workspace_id=self.workspace_id,
            target_description=description,
            patches=list(self._patches),
            has_destructive_changes=has_destructive,
            requires_manual_review=True,  # Always True
            auto_apply_allowed=False,  # Always False
        )

    def clear(self) -> None:
        """Clear pending patches."""
        self._patches = []


def generate_patchset(
    workspace_id: str,
    description: str,
    modifications: List[Dict[str, str]],
) -> Patchset:
    """
    Convenience function to generate a patchset.

    Args:
        workspace_id: Associated workspace
        description: Change description
        modifications: List of {file_path, original, new} dicts

    Returns:
        Generated Patchset (output only)
    """
    generator = PatchsetGenerator(workspace_id)

    for mod in modifications:
        generator.add_modification(
            file_path=mod["file_path"],
            original_content=mod.get("original", ""),
            new_content=mod.get("new", ""),
        )

    return generator.generate(description)
