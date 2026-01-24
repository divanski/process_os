"""
ProcessOS Configuration Migration

Handles migration from legacy configuration formats to the unified config.yaml.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from .binding import PROCESSOS_DIR, PROCESSOS_VERSION, ProjectBinding
from .config import (
    ConfigManager,
    FrameworkConfig,
    ProjectConfig,
    ProjectSettings,
    StackConfig,
)


class MigrationError(Exception):
    """Error during configuration migration."""
    pass


def migrate_to_unified_config(project_root: Path) -> Optional[ProjectConfig]:
    """
    Migrate legacy binding.yaml + fingerprint.yaml to unified config.yaml.

    Args:
        project_root: Path to project root

    Returns:
        Migrated ProjectConfig if successful, None if no legacy config exists
    """
    project_root = Path(project_root).resolve()
    processos_dir = project_root / PROCESSOS_DIR

    binding_path = processos_dir / "binding.yaml"
    fingerprint_path = processos_dir / "fingerprint.yaml"

    if not binding_path.exists():
        return None

    # Load legacy binding
    binding_data = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    binding = ProjectBinding.from_dict(binding_data)

    # Load legacy fingerprint if exists
    fingerprint_data = {}
    if fingerprint_path.exists():
        fingerprint_data = yaml.safe_load(fingerprint_path.read_text(encoding="utf-8"))

    # Convert to unified config
    now = datetime.now(timezone.utc).isoformat()

    # Convert stacks
    stacks = []
    if fingerprint_data:
        primary_stack = fingerprint_data.get("primary_stack")
        if primary_stack:
            stacks.append(StackConfig(
                stack_id=primary_stack.get("stack_id", ""),
                confidence=primary_stack.get("confidence", "medium"),
                version_hint=primary_stack.get("version"),
            ))

    # Convert frameworks
    frameworks = []
    if fingerprint_data:
        for fw in fingerprint_data.get("frameworks", []):
            frameworks.append(FrameworkConfig(
                framework_id=fw.get("framework_id", ""),
                stack=fw.get("stack", ""),
                confidence=fw.get("confidence", "medium"),
                version_hint=fw.get("version"),
            ))

    # Create unified config
    config = ProjectConfig(
        version="1.0.0",
        created_at=binding.created_at,
        updated_at=now,
        project_name=binding.project_name,
        project_root=binding.project_root,
        binding_id=binding.binding_id,
        processos_version=PROCESSOS_VERSION,
        fingerprint_id=fingerprint_data.get("fingerprint_id", binding.fingerprint_ref),
        stacks=stacks,
        frameworks=frameworks,
        settings=ProjectSettings(pillars=binding.pillars),
        migrated_from="0.7.0",
    )

    # Save unified config
    config_manager = ConfigManager(project_root)
    config_manager.save(config)

    # Rename legacy files with .legacy suffix
    _backup_legacy_file(binding_path)
    if fingerprint_path.exists():
        _backup_legacy_file(fingerprint_path)

    # Rename claude-rules to claude if it exists
    _migrate_claude_dir(processos_dir)

    return config


def _backup_legacy_file(file_path: Path) -> None:
    """Rename legacy file with .legacy suffix."""
    if file_path.exists():
        legacy_path = file_path.with_suffix(file_path.suffix + ".legacy")
        shutil.move(str(file_path), str(legacy_path))


def _migrate_claude_dir(processos_dir: Path) -> None:
    """Rename claude-rules/ to claude/ if needed."""
    old_dir = processos_dir / "claude-rules"
    new_dir = processos_dir / "claude"

    if old_dir.exists() and not new_dir.exists():
        shutil.move(str(old_dir), str(new_dir))


def can_migrate(project_root: Path) -> bool:
    """
    Check if project can be migrated.

    Args:
        project_root: Path to project root

    Returns:
        True if legacy config exists and can be migrated
    """
    processos_dir = Path(project_root).resolve() / PROCESSOS_DIR
    binding_path = processos_dir / "binding.yaml"
    config_path = processos_dir / "config.yaml"

    # Can migrate if binding exists but config doesn't
    return binding_path.exists() and not config_path.exists()


def rollback_migration(project_root: Path) -> bool:
    """
    Rollback a migration by restoring legacy files.

    Args:
        project_root: Path to project root

    Returns:
        True if rollback was successful
    """
    processos_dir = Path(project_root).resolve() / PROCESSOS_DIR

    config_path = processos_dir / "config.yaml"
    binding_legacy = processos_dir / "binding.yaml.legacy"
    fingerprint_legacy = processos_dir / "fingerprint.yaml.legacy"

    if not binding_legacy.exists():
        return False

    # Remove new config
    if config_path.exists():
        config_path.unlink()

    # Restore legacy files
    shutil.move(str(binding_legacy), str(processos_dir / "binding.yaml"))
    if fingerprint_legacy.exists():
        shutil.move(str(fingerprint_legacy), str(processos_dir / "fingerprint.yaml"))

    # Restore claude-rules if claude exists
    old_dir = processos_dir / "claude-rules"
    new_dir = processos_dir / "claude"
    if new_dir.exists() and not old_dir.exists():
        shutil.move(str(new_dir), str(old_dir))

    return True


def get_migration_status(project_root: Path) -> dict:
    """
    Get migration status for a project.

    Args:
        project_root: Path to project root

    Returns:
        Dictionary with migration status information
    """
    processos_dir = Path(project_root).resolve() / PROCESSOS_DIR

    return {
        "has_legacy_binding": (processos_dir / "binding.yaml").exists(),
        "has_legacy_fingerprint": (processos_dir / "fingerprint.yaml").exists(),
        "has_unified_config": (processos_dir / "config.yaml").exists(),
        "has_legacy_backups": (processos_dir / "binding.yaml.legacy").exists(),
        "can_migrate": can_migrate(project_root),
        "can_rollback": (processos_dir / "binding.yaml.legacy").exists(),
    }
