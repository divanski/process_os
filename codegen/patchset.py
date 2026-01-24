"""
ProcessOS Patchset Manager Module

Manages code patchset creation, review, application, and rollback.
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol

from .types import (
    FileDecision,
    GeneratedCode,
    GeneratedFile,
    Patchset,
)


class PatchsetHandler(Protocol):
    """Protocol for patchset review handlers."""

    def present_file(self, file: GeneratedFile) -> None:
        """Present a file to the user for review."""
        ...

    def get_decision(self, file: GeneratedFile) -> FileDecision:
        """Get user decision for a file."""
        ...

    def get_modification(self, file: GeneratedFile) -> str:
        """Get modified content from user."""
        ...


class PatchsetManager:
    """
    Manages patchset lifecycle: creation, review, application, rollback.

    Features:
    - Interactive file-by-file review
    - Backup creation before applying
    - Safe application with validation
    - Rollback capability
    """

    BACKUP_DIR_NAME = ".patchset_backups"

    def __init__(
        self,
        project_root: Optional[Path] = None,
        root_path: Optional[Path] = None,
        handler: Optional[PatchsetHandler] = None,
    ):
        """
        Initialize the patchset manager.

        Args:
            project_root: Root directory of the project (alias: root_path)
            root_path: Root directory of the project (alias: project_root)
            handler: Optional handler for interactive review
        """
        # Support both parameter names for compatibility
        root = project_root or root_path
        self.project_root = Path(root) if root else Path.cwd()
        self.handler = handler
        self._backup_dir = self.project_root / self.BACKUP_DIR_NAME

    def preview_patchset(
        self,
        generated_code: GeneratedCode,
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Preview what a patchset would do without creating it.

        Args:
            generated_code: GeneratedCode to preview

        Returns:
            Dict with 'new_files', 'modified_files', 'rejected_files' lists
        """
        result: Dict[str, List[Dict[str, str]]] = {
            "new_files": [],
            "modified_files": [],
            "rejected_files": [],
        }

        for file in generated_code.files:
            # Use forward slashes for cross-platform consistency
            file_path = str(file.file_path).replace("\\", "/")
            file_info = {
                "path": file_path,
                "type": file.file_type.value,
            }

            if file.user_decision == FileDecision.REJECT:
                result["rejected_files"].append(file_info)
            elif file.is_modification:
                result["modified_files"].append(file_info)
            else:
                result["new_files"].append(file_info)

        return result

    def create_patchset(
        self,
        generated_code: GeneratedCode,
        patchset_id: Optional[str] = None,
        create_backup: bool = False,
    ) -> Patchset:
        """
        Create a patchset from reviewed generated code.

        Args:
            generated_code: GeneratedCode with all files decided
            patchset_id: Optional custom ID (generated if not provided)

        Returns:
            Patchset ready for application

        Raises:
            ValueError: If generated code has pending decisions
        """
        if not generated_code.all_decided:
            raise ValueError("Cannot create patchset with pending file decisions")

        patchset_id = patchset_id or str(uuid.uuid4())[:8]
        return Patchset.from_generated_code(patchset_id, generated_code)

    def review_interactive(
        self,
        generated_code: GeneratedCode,
        handler: Optional[PatchsetHandler] = None,
        auto_accept_all: bool = False,
    ) -> GeneratedCode:
        """
        Run interactive review workflow for generated code.

        Args:
            generated_code: Code to review
            handler: Optional handler (uses self.handler if not provided)
            auto_accept_all: If True, accept all files without prompting

        Returns:
            Updated GeneratedCode with all decisions made

        Raises:
            ValueError: If no handler provided and not auto_accept_all
        """
        if auto_accept_all:
            for file in generated_code.pending_review:
                file.accept()
            generated_code.complete_review()
            return generated_code

        handler = handler or self.handler
        if not handler:
            raise ValueError("No handler provided for interactive review")

        generated_code.start_review()

        for file in generated_code.pending_review:
            handler.present_file(file)
            decision = handler.get_decision(file)

            if decision == FileDecision.ACCEPT:
                file.accept()
            elif decision == FileDecision.REJECT:
                file.reject()
            elif decision == FileDecision.MODIFY:
                new_content = handler.get_modification(file)
                file.modify(new_content)

        generated_code.complete_review()
        return generated_code

    def apply_patchset(
        self,
        patchset: Patchset,
        create_backup: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, str]:
        """
        Apply a patchset to the project.

        Args:
            patchset: Patchset to apply
            create_backup: Whether to create backup before applying
            dry_run: If True, validate but don't write files

        Returns:
            Dict mapping file paths to status ('created', 'modified', 'skipped')

        Raises:
            ApplyError: If application fails
        """
        from . import ApplyError

        results: Dict[str, str] = {}
        backup_path: Optional[Path] = None

        # Create backup if requested
        if create_backup and not dry_run:
            backup_path = self._create_backup(patchset)

        for file in patchset.files:
            target_path = self.project_root / file.file_path

            try:
                if dry_run:
                    if target_path.exists():
                        results[str(file.file_path)] = "would_modify"
                    else:
                        results[str(file.file_path)] = "would_create"
                    continue

                # Ensure parent directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write the file
                if target_path.exists():
                    target_path.write_text(file.final_content, encoding="utf-8")
                    results[str(file.file_path)] = "modified"
                else:
                    target_path.write_text(file.final_content, encoding="utf-8")
                    results[str(file.file_path)] = "created"

            except OSError as e:
                # Clean up partial application if backup exists
                if backup_path and backup_path.exists():
                    self._restore_from_backup(backup_path)
                raise ApplyError(str(file.file_path), str(e))

        if not dry_run:
            patchset.apply(str(backup_path) if backup_path else None)

        return results

    def _create_backup(self, patchset: Patchset) -> Path:
        """
        Create a backup of files that will be modified.

        Args:
            patchset: Patchset about to be applied

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"{patchset.id}_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        # Backup existing files that will be modified
        for file in patchset.files:
            source_path = self.project_root / file.file_path
            if source_path.exists():
                backup_file = backup_path / file.file_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, backup_file)

        # Save patchset metadata
        metadata = {
            "patchset_id": patchset.id,
            "created_at": datetime.now().isoformat(),
            "files": [str(f.file_path) for f in patchset.files],
        }
        (backup_path / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        return backup_path

    def rollback(self, patchset: Patchset) -> bool:
        """
        Rollback a patchset using its backup.

        Args:
            patchset: Patchset to rollback

        Returns:
            True if rollback succeeded, False if no backup available

        Raises:
            ApplyError: If rollback fails
        """
        if not patchset.rollback_available or not patchset.rollback_snapshot:
            return False

        backup_path = Path(patchset.rollback_snapshot)
        if not backup_path.exists():
            return False

        return self._restore_from_backup(backup_path)

    def rollback_patchset(self, patchset: Patchset) -> bool:
        """Alias for rollback() for API compatibility."""
        return self.rollback(patchset)

    def _restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore files from a backup directory.

        Args:
            backup_path: Path to backup directory

        Returns:
            True if restoration succeeded
        """
        from . import ApplyError

        metadata_file = backup_path / "metadata.json"
        if not metadata_file.exists():
            return False

        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        for file_path_str in metadata.get("files", []):
            backup_file = backup_path / file_path_str
            target_file = self.project_root / file_path_str

            if backup_file.exists():
                # Restore from backup
                try:
                    shutil.copy2(backup_file, target_file)
                except OSError as e:
                    raise ApplyError(file_path_str, f"Rollback failed: {e}")
            elif target_file.exists():
                # File was created (not modified), so remove it
                try:
                    target_file.unlink()
                except OSError as e:
                    raise ApplyError(file_path_str, f"Rollback failed: {e}")

        return True

    def list_backups(self) -> List[Dict]:
        """
        List all available backups.

        Returns:
            List of backup metadata dicts
        """
        backups = []

        if not self._backup_dir.exists():
            return backups

        for backup_path in self._backup_dir.iterdir():
            if backup_path.is_dir():
                metadata_file = backup_path / "metadata.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    metadata["backup_path"] = str(backup_path)
                    backups.append(metadata)

        return sorted(backups, key=lambda x: x.get("created_at", ""), reverse=True)

    def cleanup_backups(self, keep_count: int = 5) -> int:
        """
        Clean up old backups, keeping the most recent.

        Args:
            keep_count: Number of recent backups to keep

        Returns:
            Number of backups removed
        """
        backups = self.list_backups()

        if len(backups) <= keep_count:
            return 0

        removed = 0
        for backup in backups[keep_count:]:
            backup_path = Path(backup["backup_path"])
            if backup_path.exists():
                shutil.rmtree(backup_path)
                removed += 1

        return removed

    def format_file(self, file: GeneratedFile) -> str:
        """
        Format a file for display during review.

        Args:
            file: GeneratedFile to format

        Returns:
            Formatted string for display
        """
        lines = [
            f"File: {file.file_path}",
            f"Type: {file.file_type.value}",
        ]

        if file.is_modification:
            lines.append("Action: Modify existing file")
            if file.diff:
                lines.append("Changes:")
                lines.append(file.diff)
        else:
            lines.append("Action: Create new file")
            # Show preview of content (first 20 lines)
            preview_lines = file.content.split("\n")[:20]
            lines.append("Preview:")
            lines.extend(f"  {line}" for line in preview_lines)
            if len(file.content.split("\n")) > 20:
                lines.append("  ... (truncated)")

        return "\n".join(lines)


class ConsolePatchsetHandler:
    """
    Console-based patchset handler for CLI usage.
    """

    def __init__(self, manager: Optional[PatchsetManager] = None):
        """
        Initialize the console handler.

        Args:
            manager: Optional PatchsetManager for formatting
        """
        self.manager = manager

    def present_file(self, file: GeneratedFile) -> None:
        """Present file to console."""
        print("\n" + "=" * 60)
        if self.manager:
            print(self.manager.format_file(file))
        else:
            print(f"File: {file.file_path}")
            print(f"Type: {file.file_type.value}")
            if file.is_modification:
                print("Action: Modify")
            else:
                print("Action: Create")

    def get_decision(self, file: GeneratedFile) -> FileDecision:
        """Get user decision from console."""
        print("\nOptions:")
        print("  [a] Accept this file")
        print("  [r] Reject this file")
        print("  [m] Modify content")
        print("  [v] View full content")
        print()

        while True:
            choice = input("Your choice [a/r/m/v]: ").strip().lower()

            if choice == "a":
                return FileDecision.ACCEPT
            elif choice == "r":
                return FileDecision.REJECT
            elif choice == "m":
                return FileDecision.MODIFY
            elif choice == "v":
                print("\n" + "-" * 40)
                print(file.content)
                print("-" * 40 + "\n")
            else:
                print("Invalid choice. Please enter 'a', 'r', 'm', or 'v'")

    def get_modification(self, file: GeneratedFile) -> str:
        """Get modified content from user."""
        print("\nCurrent content:")
        print("-" * 40)
        print(file.content)
        print("-" * 40)
        print("\nEnter modified content (enter 'END' on a new line when done):")

        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)

        return "\n".join(lines)
