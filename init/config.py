"""
ProcessOS Project Configuration

Unified configuration management for ProcessOS projects.
Replaces separate binding.yaml and fingerprint.yaml with a single config.yaml.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .binding import PROCESSOS_DIR, PROCESSOS_VERSION


@dataclass
class StackConfig:
    """Detected stack configuration."""
    stack_id: str
    confidence: str  # "high" | "medium" | "low"
    version_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = {"stack_id": self.stack_id, "confidence": self.confidence}
        if self.version_hint:
            d["version_hint"] = self.version_hint
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StackConfig":
        """Create from dictionary."""
        return cls(
            stack_id=data["stack_id"],
            confidence=data.get("confidence", "medium"),
            version_hint=data.get("version_hint"),
        )


@dataclass
class FrameworkConfig:
    """Detected framework configuration."""
    framework_id: str
    stack: str  # Parent stack ID
    confidence: str  # "high" | "medium" | "low"
    version_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = {
            "framework_id": self.framework_id,
            "stack": self.stack,
            "confidence": self.confidence,
        }
        if self.version_hint:
            d["version_hint"] = self.version_hint
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameworkConfig":
        """Create from dictionary."""
        return cls(
            framework_id=data["framework_id"],
            stack=data["stack"],
            confidence=data.get("confidence", "medium"),
            version_hint=data.get("version_hint"),
        )


@dataclass
class ObservabilitySettings:
    """Observability configuration."""
    mode: str = "minimal"  # "minimal" | "full" | "silent"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"mode": self.mode}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservabilitySettings":
        """Create from dictionary."""
        return cls(mode=data.get("mode", "minimal"))


@dataclass
class CISettings:
    """CI/CD integration settings (T051, T052)."""
    detected: bool = False
    provider: Optional[str] = None
    output_mode: str = "auto"  # "auto" | "ci" | "interactive"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d: Dict[str, Any] = {"output_mode": self.output_mode}
        if self.detected:
            d["detected"] = self.detected
            if self.provider:
                d["provider"] = self.provider
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CISettings":
        """Create from dictionary."""
        return cls(
            detected=data.get("detected", False),
            provider=data.get("provider"),
            output_mode=data.get("output_mode", "auto"),
        )


@dataclass
class CredentialSettings:
    """Credential configuration."""
    sources: List[str] = field(default_factory=lambda: ["env", "keychain", "file"])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"sources": self.sources}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CredentialSettings":
        """Create from dictionary."""
        return cls(sources=data.get("sources", ["env", "keychain", "file"]))


@dataclass
class TeamConfig:
    """Team configuration inheritance support (T053)."""
    inherit_from: Optional[str] = None  # Path to team config file
    override_allowed: List[str] = field(default_factory=list)  # Paths that can be overridden

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d: Dict[str, Any] = {}
        if self.inherit_from:
            d["inherit_from"] = self.inherit_from
        if self.override_allowed:
            d["override_allowed"] = self.override_allowed
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamConfig":
        """Create from dictionary."""
        return cls(
            inherit_from=data.get("inherit_from"),
            override_allowed=data.get("override_allowed", []),
        )


@dataclass
class ProjectSettings:
    """Project-wide settings."""
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    credentials: CredentialSettings = field(default_factory=CredentialSettings)
    ci: CISettings = field(default_factory=CISettings)
    team: TeamConfig = field(default_factory=TeamConfig)
    pillars: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d: Dict[str, Any] = {
            "observability": self.observability.to_dict(),
            "credentials": self.credentials.to_dict(),
            "pillars": self.pillars,
        }
        # Only include CI if detected
        ci_dict = self.ci.to_dict()
        if ci_dict.get("detected") or ci_dict.get("output_mode") != "auto":
            d["ci"] = ci_dict
        # Only include team if configured
        team_dict = self.team.to_dict()
        if team_dict:
            d["team"] = team_dict
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectSettings":
        """Create from dictionary."""
        return cls(
            observability=ObservabilitySettings.from_dict(data.get("observability", {})),
            credentials=CredentialSettings.from_dict(data.get("credentials", {})),
            ci=CISettings.from_dict(data.get("ci", {})),
            team=TeamConfig.from_dict(data.get("team", {})),
            pillars=data.get("pillars", []),
        )


@dataclass
class ProjectConfig:
    """
    Unified project configuration for ProcessOS.

    Combines binding, fingerprint, and settings into a single config.yaml.
    """
    # Schema version
    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""

    # Project info
    project_name: str = ""
    project_root: str = "."

    # Binding info
    binding_id: str = ""
    processos_version: str = PROCESSOS_VERSION

    # Fingerprint info
    fingerprint_id: str = ""
    stacks: List[StackConfig] = field(default_factory=list)
    frameworks: List[FrameworkConfig] = field(default_factory=list)
    fingerprint_details: Optional[Dict[str, Any]] = None  # Detailed version info

    # Settings
    settings: ProjectSettings = field(default_factory=ProjectSettings)

    # Migration tracking
    migrated_from: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        fingerprint_dict: Dict[str, Any] = {
            "fingerprint_id": self.fingerprint_id,
            "stacks": [s.to_dict() for s in self.stacks],
            "frameworks": [f.to_dict() for f in self.frameworks],
        }
        if self.fingerprint_details:
            fingerprint_dict["details"] = self.fingerprint_details

        d: Dict[str, Any] = {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project": {
                "name": self.project_name,
                "root": self.project_root,
            },
            "binding": {
                "binding_id": self.binding_id,
                "processos_version": self.processos_version,
            },
            "fingerprint": fingerprint_dict,
            "settings": self.settings.to_dict(),
        }
        if self.migrated_from:
            d["_migration"] = {"from_version": self.migrated_from}
        return d

    def to_yaml(self) -> str:
        """Serialize to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Create from dictionary."""
        project = data.get("project", {})
        binding = data.get("binding", {})
        fingerprint = data.get("fingerprint", {})
        migration = data.get("_migration", {})

        return cls(
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            project_name=project.get("name", ""),
            project_root=project.get("root", "."),
            binding_id=binding.get("binding_id", ""),
            processos_version=binding.get("processos_version", PROCESSOS_VERSION),
            fingerprint_id=fingerprint.get("fingerprint_id", ""),
            stacks=[StackConfig.from_dict(s) for s in fingerprint.get("stacks", [])],
            frameworks=[FrameworkConfig.from_dict(f) for f in fingerprint.get("frameworks", [])],
            fingerprint_details=fingerprint.get("details"),
            settings=ProjectSettings.from_dict(data.get("settings", {})),
            migrated_from=migration.get("from_version"),
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "ProjectConfig":
        """Create from YAML string."""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)


class ConfigManager:
    """
    Manages unified config.yaml files in ProcessOS projects.

    Handles loading, saving, and updating project configuration.
    Supports migration from legacy binding.yaml + fingerprint.yaml format.
    """

    def __init__(self, project_root: Path):
        """
        Initialize the config manager.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root).resolve()
        self.processos_dir = self.project_root / PROCESSOS_DIR
        self.config_path = self.processos_dir / "config.yaml"

    @property
    def is_initialized(self) -> bool:
        """Check if project has ProcessOS configuration."""
        return self.config_path.exists() or self._has_legacy_config()

    def _has_legacy_config(self) -> bool:
        """Check if project has legacy configuration files."""
        return (self.processos_dir / "binding.yaml").exists()

    def load(self) -> Optional[ProjectConfig]:
        """
        Load project configuration.

        Returns:
            ProjectConfig if config exists, None otherwise
        """
        if self.config_path.exists():
            content = self.config_path.read_text(encoding="utf-8")
            return ProjectConfig.from_yaml(content)

        # Try migration from legacy format
        if self._has_legacy_config():
            from .migration import migrate_to_unified_config
            return migrate_to_unified_config(self.project_root)

        return None

    def save(self, config: ProjectConfig) -> Path:
        """
        Save project configuration.

        Args:
            config: Configuration to save

        Returns:
            Path to saved config file
        """
        self.processos_dir.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        config.updated_at = datetime.now(timezone.utc).isoformat()

        self.config_path.write_text(config.to_yaml(), encoding="utf-8")
        return self.config_path

    def create(
        self,
        project_name: Optional[str] = None,
        stacks: Optional[List[StackConfig]] = None,
        frameworks: Optional[List[FrameworkConfig]] = None,
        pillars: Optional[List[str]] = None,
        fingerprint_details: Optional[Dict[str, Any]] = None,
    ) -> ProjectConfig:
        """
        Create a new project configuration.

        Args:
            project_name: Optional project name (defaults to directory name)
            stacks: Detected stacks
            frameworks: Detected frameworks
            pillars: Active pillars
            fingerprint_details: Detailed version info from VersionExtractor

        Returns:
            New ProjectConfig
        """
        now = datetime.now(timezone.utc).isoformat()
        name = project_name or self.project_root.name

        # Generate IDs
        fingerprint_id = self._generate_fingerprint_id(stacks or [], frameworks or [])
        binding_id = self._generate_binding_id(fingerprint_id)

        config = ProjectConfig(
            version="1.0.0",
            created_at=now,
            updated_at=now,
            project_name=name,
            project_root=".",
            binding_id=binding_id,
            processos_version=PROCESSOS_VERSION,
            fingerprint_id=fingerprint_id,
            stacks=stacks or [],
            frameworks=frameworks or [],
            fingerprint_details=fingerprint_details,
            settings=ProjectSettings(pillars=pillars or []),
        )

        return config

    def _generate_fingerprint_id(
        self, stacks: List[StackConfig], frameworks: List[FrameworkConfig]
    ) -> str:
        """Generate fingerprint ID from detected stacks and frameworks."""
        # Create deterministic hash from stack/framework data
        items = []
        for s in sorted(stacks, key=lambda x: x.stack_id):
            items.append(f"stack:{s.stack_id}:{s.confidence}")
        for f in sorted(frameworks, key=lambda x: x.framework_id):
            items.append(f"framework:{f.framework_id}:{f.stack}:{f.confidence}")

        hash_input = "|".join(items) or "empty"
        content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return f"fp-{content_hash[:12]}"

    def _generate_binding_id(self, fingerprint_id: str) -> str:
        """Generate binding ID from fingerprint."""
        hash_input = f"binding:{fingerprint_id}:{PROCESSOS_VERSION}"
        content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return f"bind-{content_hash[:12]}"

    def update_setting(self, path: str, value: Any) -> ProjectConfig:
        """
        Update a setting in the configuration.

        Args:
            path: Dot-separated path (e.g., "settings.observability.mode")
            value: New value

        Returns:
            Updated configuration

        Raises:
            ValueError: If path is invalid
        """
        config = self.load()
        if config is None:
            raise ValueError("Project not initialized. Run 'processos init' first.")

        parts = path.split(".")
        self._set_nested_value(config, parts, value)
        self.save(config)
        return config

    def _set_nested_value(self, obj: Any, path: List[str], value: Any) -> None:
        """Set a nested value on an object."""
        if len(path) == 1:
            if hasattr(obj, path[0]):
                setattr(obj, path[0], value)
            elif isinstance(obj, dict):
                obj[path[0]] = value
            else:
                raise ValueError(f"Cannot set '{path[0]}' on {type(obj).__name__}")
        else:
            next_obj = getattr(obj, path[0], None)
            if next_obj is None and isinstance(obj, dict):
                next_obj = obj.get(path[0])
            if next_obj is None:
                raise ValueError(f"Path not found: {path[0]}")
            self._set_nested_value(next_obj, path[1:], value)

    def get_claude_dir(self) -> Path:
        """Get path to Claude instructions directory (renamed from claude-rules)."""
        return self.processos_dir / "claude"

    def get_value(self, path: str) -> Any:
        """
        Get a value from the configuration (T048).

        Args:
            path: Dot-separated path (e.g., "settings.observability.mode")

        Returns:
            Value at path

        Raises:
            ValueError: If path is invalid or config not loaded
        """
        config = self.load()
        if config is None:
            raise ValueError("Project not initialized. Run 'processos init' first.")

        return self._get_nested_value(config, path.split("."))

    def _get_nested_value(self, obj: Any, path: List[str]) -> Any:
        """Get a nested value from an object."""
        if not path:
            return obj

        key = path[0]
        if hasattr(obj, key):
            next_obj = getattr(obj, key)
        elif isinstance(obj, dict):
            next_obj = obj.get(key)
        else:
            raise ValueError(f"Path not found: {key}")

        if next_obj is None:
            raise ValueError(f"Path not found: {key}")

        return self._get_nested_value(next_obj, path[1:])

    def validate(self, fix: bool = False) -> "ConfigValidationResult":
        """
        Validate project configuration (T050).

        Args:
            fix: Automatically fix fixable issues

        Returns:
            ConfigValidationResult with issues and fixes applied
        """
        issues: List[ConfigIssue] = []
        fixes_applied: List[str] = []
        config = self.load()

        if config is None:
            issues.append(ConfigIssue(
                level="error",
                path="",
                message="No configuration found",
                fixable=False,
            ))
            return ConfigValidationResult(
                valid=False,
                issues=issues,
                fixes_applied=fixes_applied,
            )

        # Validate required fields
        if not config.project_name:
            if fix:
                config.project_name = self.project_root.name
                fixes_applied.append(f"Set project_name to '{config.project_name}'")
            else:
                issues.append(ConfigIssue(
                    level="error",
                    path="project.name",
                    message="Project name is required",
                    fixable=True,
                ))

        if not config.binding_id:
            if fix:
                config.binding_id = self._generate_binding_id(config.fingerprint_id or "unknown")
                fixes_applied.append(f"Generated binding_id: {config.binding_id}")
            else:
                issues.append(ConfigIssue(
                    level="error",
                    path="binding.binding_id",
                    message="Binding ID is required",
                    fixable=True,
                ))

        if not config.fingerprint_id:
            if fix:
                config.fingerprint_id = self._generate_fingerprint_id(config.stacks, config.frameworks)
                fixes_applied.append(f"Generated fingerprint_id: {config.fingerprint_id}")
            else:
                issues.append(ConfigIssue(
                    level="error",
                    path="fingerprint.fingerprint_id",
                    message="Fingerprint ID is required",
                    fixable=True,
                ))

        # Validate version format
        if config.version and not self._is_valid_version(config.version):
            issues.append(ConfigIssue(
                level="warning",
                path="version",
                message=f"Invalid version format: {config.version} (expected semver)",
                fixable=False,
            ))

        # Validate observability mode
        valid_modes = ["minimal", "full", "silent"]
        if config.settings.observability.mode not in valid_modes:
            if fix:
                config.settings.observability.mode = "minimal"
                fixes_applied.append("Reset observability.mode to 'minimal'")
            else:
                issues.append(ConfigIssue(
                    level="error",
                    path="settings.observability.mode",
                    message=f"Invalid mode: {config.settings.observability.mode} (valid: {valid_modes})",
                    fixable=True,
                ))

        # Validate credential sources
        valid_sources = ["env", "keychain", "file"]
        invalid_sources = [s for s in config.settings.credentials.sources if s not in valid_sources]
        if invalid_sources:
            if fix:
                config.settings.credentials.sources = [
                    s for s in config.settings.credentials.sources if s in valid_sources
                ]
                fixes_applied.append(f"Removed invalid credential sources: {invalid_sources}")
            else:
                for source in invalid_sources:
                    issues.append(ConfigIssue(
                        level="warning",
                        path="settings.credentials.sources",
                        message=f"Unknown credential source: {source}",
                        fixable=True,
                    ))

        # Validate stacks have required fields
        for i, stack in enumerate(config.stacks):
            if not stack.stack_id:
                issues.append(ConfigIssue(
                    level="error",
                    path=f"fingerprint.stacks[{i}].stack_id",
                    message="Stack ID is required",
                    fixable=False,
                ))
            if stack.confidence not in ["high", "medium", "low"]:
                if fix:
                    stack.confidence = "medium"
                    fixes_applied.append(f"Set stacks[{i}].confidence to 'medium'")
                else:
                    issues.append(ConfigIssue(
                        level="warning",
                        path=f"fingerprint.stacks[{i}].confidence",
                        message=f"Invalid confidence: {stack.confidence} (valid: high, medium, low)",
                        fixable=True,
                    ))

        # Check for legacy claude-rules directory and suggest migration
        legacy_rules_dir = self.processos_dir / "claude-rules"
        if legacy_rules_dir.exists():
            if fix:
                import shutil
                claude_dir = self.get_claude_dir()
                if not claude_dir.exists():
                    shutil.move(str(legacy_rules_dir), str(claude_dir))
                    fixes_applied.append("Migrated claude-rules/ to claude/")
                else:
                    issues.append(ConfigIssue(
                        level="warning",
                        path="",
                        message="Both claude-rules/ and claude/ exist. Remove claude-rules/ manually.",
                        fixable=False,
                    ))
            else:
                issues.append(ConfigIssue(
                    level="warning",
                    path="",
                    message="Legacy claude-rules/ directory found. Run with --fix to migrate to claude/",
                    fixable=True,
                ))

        # Save fixed config
        if fix and fixes_applied:
            self.save(config)

        # Determine overall validity
        has_errors = any(issue.level == "error" for issue in issues)
        valid = not has_errors

        return ConfigValidationResult(
            valid=valid,
            issues=issues,
            fixes_applied=fixes_applied,
            config=config,
        )

    def _is_valid_version(self, version: str) -> bool:
        """Check if version string is valid semver."""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?$"
        return bool(re.match(pattern, version))


@dataclass
class ConfigIssue:
    """A validation issue found in configuration."""
    level: str  # "error" | "warning" | "info"
    path: str   # Dot-separated path to the issue
    message: str
    fixable: bool = False


@dataclass
class ConfigValidationResult:
    """Result of configuration validation (T050)."""
    valid: bool
    issues: List[ConfigIssue] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    config: Optional[ProjectConfig] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "valid": self.valid,
            "issues": [
                {"level": i.level, "path": i.path, "message": i.message, "fixable": i.fixable}
                for i in self.issues
            ],
            "fixes_applied": self.fixes_applied,
        }

    def format(self) -> str:
        """Format for human-readable output."""
        lines = []

        if self.valid and not self.issues:
            lines.append("Configuration is valid.")
        elif self.valid:
            lines.append("Configuration is valid with warnings.")
        else:
            lines.append("Configuration has errors.")

        if self.issues:
            lines.append("")
            for issue in self.issues:
                prefix = {"error": "[ERROR]", "warning": "[WARN]", "info": "[INFO]"}.get(issue.level, "[?]")
                fix_hint = " (fixable with --fix)" if issue.fixable else ""
                path_hint = f" at {issue.path}" if issue.path else ""
                lines.append(f"{prefix}{path_hint}: {issue.message}{fix_hint}")

        if self.fixes_applied:
            lines.append("")
            lines.append("Fixes applied:")
            for fix in self.fixes_applied:
                lines.append(f"  - {fix}")

        return "\n".join(lines)
