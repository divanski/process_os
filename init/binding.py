"""
ProcessOS Project Binding

Manages project binding files in .processos/ directory.
"""

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from process_os.stack_fingerprint import StackFingerprint


# ProcessOS version
PROCESSOS_VERSION = "0.9.0"

# Directory name for ProcessOS files
PROCESSOS_DIR = ".processos"


def get_processos_home() -> Optional[Path]:
    """
    Get ProcessOS home directory from environment (T054).

    The PROCESSOS_HOME environment variable allows:
    - Shared team configurations
    - Global ProcessOS settings
    - Plugin/extension storage

    Returns:
        Path to PROCESSOS_HOME if set, None otherwise
    """
    home_env = os.environ.get("PROCESSOS_HOME")
    if home_env:
        home_path = Path(home_env).expanduser().resolve()
        if home_path.exists():
            return home_path
    return None


def get_global_config_path() -> Optional[Path]:
    """
    Get path to global ProcessOS configuration.

    Checks:
    1. PROCESSOS_HOME/config.yaml
    2. ~/.processos/config.yaml (fallback)

    Returns:
        Path to global config if exists, None otherwise
    """
    # Check PROCESSOS_HOME first
    home = get_processos_home()
    if home:
        config_path = home / "config.yaml"
        if config_path.exists():
            return config_path

    # Fallback to ~/.processos/
    user_config = Path.home() / ".processos" / "config.yaml"
    if user_config.exists():
        return user_config

    return None


def get_team_config_path(team_config_ref: str, project_root: Path) -> Optional[Path]:
    """
    Resolve team config path (T053).

    Supports:
    - Relative paths (relative to project root)
    - Absolute paths
    - PROCESSOS_HOME references (e.g., "$PROCESSOS_HOME/teams/myteam.yaml")

    Args:
        team_config_ref: Team config reference string
        project_root: Project root directory

    Returns:
        Resolved path if exists, None otherwise
    """
    if team_config_ref.startswith("$PROCESSOS_HOME/"):
        home = get_processos_home()
        if home:
            relative = team_config_ref[len("$PROCESSOS_HOME/"):]
            config_path = home / relative
            if config_path.exists():
                return config_path
        return None

    # Try as absolute path
    if os.path.isabs(team_config_ref):
        config_path = Path(team_config_ref)
        if config_path.exists():
            return config_path
        return None

    # Try as relative path from project root
    config_path = project_root / team_config_ref
    if config_path.exists():
        return config_path

    return None


@dataclass
class ProjectBinding:
    """
    Project binding configuration.

    Links a project to ProcessOS with fingerprint.
    NOTE: Integrations are now managed dynamically by the Dynamic Integration Engine.
    """

    binding_id: str
    created_at: str
    processos_version: str
    fingerprint_ref: str
    project_name: str
    project_root: str
    integrations: List[str] = field(default_factory=list)  # Dynamic integrations (replaces pillars)
    rules_pack: str = f"{PROCESSOS_DIR}/claude-rules/"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "binding_id": self.binding_id,
            "created_at": self.created_at,
            "processos_version": self.processos_version,
            "fingerprint_ref": self.fingerprint_ref,
            "project": {
                "name": self.project_name,
                "root": self.project_root,
            },
            "integrations": self.integrations,
            "rules_pack": self.rules_pack,
        }

    def to_yaml(self) -> str:
        """Serialize to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectBinding":
        """Create from dictionary."""
        project = data.get("project", {})
        # Support both old 'pillars' and new 'integrations' for backward compatibility
        integrations = data.get("integrations", data.get("pillars", []))
        return cls(
            binding_id=data["binding_id"],
            created_at=data["created_at"],
            processos_version=data["processos_version"],
            fingerprint_ref=data["fingerprint_ref"],
            project_name=project.get("name", ""),
            project_root=project.get("root", "."),
            integrations=integrations,
            rules_pack=data.get("rules_pack", f"{PROCESSOS_DIR}/claude-rules/"),
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "ProjectBinding":
        """Create from YAML string."""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)


class BindingGenerator:
    """
    Generates project bindings.

    Key invariant: same fingerprint → same binding_id
    """

    def generate(
        self,
        fingerprint: StackFingerprint,
        project_name: Optional[str] = None,
        integrations: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ) -> ProjectBinding:
        """
        Generate binding for a project.

        Args:
            fingerprint: Stack fingerprint for the project
            project_name: Optional project name (defaults to directory name)
            integrations: Optional list of active integrations (dynamically managed)
            timestamp: Optional fixed timestamp

        Returns:
            ProjectBinding
        """
        # Extract project root from fingerprint
        project_root = Path(fingerprint.project_root)

        # Default project name to directory name
        if not project_name:
            project_name = project_root.name

        # Generate deterministic binding ID
        binding_id = self._generate_binding_id(fingerprint.fingerprint_id)

        # Use provided timestamp or current time
        created_at = timestamp or datetime.now(timezone.utc).isoformat()

        return ProjectBinding(
            binding_id=binding_id,
            created_at=created_at,
            processos_version=PROCESSOS_VERSION,
            fingerprint_ref=fingerprint.fingerprint_id,
            project_name=project_name,
            project_root=".",
            integrations=integrations or [],
        )

    def _generate_binding_id(self, fingerprint_id: str) -> str:
        """Generate deterministic binding ID from fingerprint."""
        hash_input = f"binding:{fingerprint_id}:{PROCESSOS_VERSION}"
        content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return f"bind-{content_hash[:12]}"


class BindingManager:
    """
    Manages binding files in a project.
    """

    def __init__(self, project_root: Path):
        """
        Initialize manager.

        Args:
            project_root: Path to project root
        """
        self.project_root = Path(project_root).resolve()
        self.processos_dir = self.project_root / PROCESSOS_DIR

    def exists(self) -> bool:
        """Check if binding exists."""
        return (self.processos_dir / "binding.yaml").exists()

    def load_binding(self) -> Optional[ProjectBinding]:
        """Load existing binding."""
        binding_path = self.processos_dir / "binding.yaml"
        if not binding_path.exists():
            return None

        content = binding_path.read_text(encoding="utf-8")
        return ProjectBinding.from_yaml(content)

    def load_fingerprint(self) -> Optional[StackFingerprint]:
        """Load existing fingerprint."""
        fingerprint_path = self.processos_dir / "fingerprint.yaml"
        if not fingerprint_path.exists():
            return None

        content = fingerprint_path.read_text(encoding="utf-8")
        return StackFingerprint.from_yaml(content)

    def save_binding(self, binding: ProjectBinding) -> Path:
        """Save binding to file."""
        self.processos_dir.mkdir(parents=True, exist_ok=True)

        binding_path = self.processos_dir / "binding.yaml"
        binding_path.write_text(binding.to_yaml(), encoding="utf-8")
        return binding_path

    def save_fingerprint(self, fingerprint: StackFingerprint) -> Path:
        """Save fingerprint to file."""
        self.processos_dir.mkdir(parents=True, exist_ok=True)

        fingerprint_path = self.processos_dir / "fingerprint.yaml"
        fingerprint_path.write_text(fingerprint.to_yaml(), encoding="utf-8")
        return fingerprint_path

    def get_rules_dir(self) -> Path:
        """Get path to rules directory."""
        return self.processos_dir / "claude-rules"


def generate_binding(
    fingerprint: StackFingerprint,
    project_name: Optional[str] = None,
    integrations: Optional[List[str]] = None,
    timestamp: Optional[str] = None,
) -> ProjectBinding:
    """
    Convenience function to generate a binding.

    Args:
        fingerprint: Stack fingerprint
        project_name: Optional project name
        integrations: Optional active integrations (dynamically managed)
        timestamp: Optional fixed timestamp

    Returns:
        ProjectBinding
    """
    generator = BindingGenerator()
    return generator.generate(
        fingerprint=fingerprint,
        project_name=project_name,
        integrations=integrations,
        timestamp=timestamp,
    )
