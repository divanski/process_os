"""
ProcessOS Project Initializer

Main initialization logic for binding ProcessOS to a project.
Supports both legacy (binding.yaml + fingerprint.yaml) and unified (config.yaml) formats.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from process_os.stack_fingerprint import FingerprintGenerator, StackFingerprint


# CI environment detection (T051)
CI_ENV_VARS = [
    "CI",                    # Generic CI
    "GITHUB_ACTIONS",        # GitHub Actions
    "GITLAB_CI",             # GitLab CI
    "JENKINS_URL",           # Jenkins
    "CIRCLECI",              # CircleCI
    "TRAVIS",                # Travis CI
    "AZURE_PIPELINES",       # Azure Pipelines
    "TF_BUILD",              # Azure DevOps
    "CODEBUILD_BUILD_ID",    # AWS CodeBuild
    "BITBUCKET_BUILD_NUMBER",  # Bitbucket Pipelines
    "BUILDKITE",             # Buildkite
    "DRONE",                 # Drone CI
    "TEAMCITY_VERSION",      # TeamCity
    "HEROKU_TEST_RUN_ID",    # Heroku CI
]


def detect_ci_environment() -> Optional[str]:
    """
    Detect if running in a CI environment (T051).

    Returns:
        CI provider name if detected, None otherwise
    """
    # Check specific CI providers first for better identification
    if os.environ.get("GITHUB_ACTIONS"):
        return "github-actions"
    if os.environ.get("GITLAB_CI"):
        return "gitlab-ci"
    if os.environ.get("JENKINS_URL"):
        return "jenkins"
    if os.environ.get("CIRCLECI"):
        return "circleci"
    if os.environ.get("TRAVIS"):
        return "travis-ci"
    if os.environ.get("AZURE_PIPELINES") or os.environ.get("TF_BUILD"):
        return "azure-pipelines"
    if os.environ.get("CODEBUILD_BUILD_ID"):
        return "aws-codebuild"
    if os.environ.get("BITBUCKET_BUILD_NUMBER"):
        return "bitbucket-pipelines"
    if os.environ.get("BUILDKITE"):
        return "buildkite"
    if os.environ.get("DRONE"):
        return "drone"
    if os.environ.get("TEAMCITY_VERSION"):
        return "teamcity"

    # Generic CI check
    if os.environ.get("CI"):
        return "unknown-ci"

    return None


def is_ci_environment() -> bool:
    """Check if running in any CI environment."""
    return detect_ci_environment() is not None

from .binding import (
    PROCESSOS_DIR,
    BindingGenerator,
    BindingManager,
    ProjectBinding,
)
from .config import (
    ConfigManager,
    FrameworkConfig,
    ProjectConfig,
    StackConfig,
)


class InitResult(Enum):
    """Result of initialization."""

    SUCCESS = 0
    ALREADY_EXISTS = 1
    DETECTION_FAILED = 2
    WRITE_ERROR = 3


@dataclass
class InitOutput:
    """Output from initialization."""

    result: InitResult
    binding: Optional[ProjectBinding] = None
    fingerprint: Optional[StackFingerprint] = None
    rules_dir: Optional[Path] = None
    message: str = ""
    # v0.8.0+ unified config support
    config: Optional[ProjectConfig] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output (T025)."""
        data: Dict[str, Any] = {
            "result": self.result.name,
            "message": self.message,
        }

        if self.config:
            data["config"] = self.config.to_dict()
        elif self.binding:
            data["binding"] = self.binding.to_dict()

        if self.fingerprint:
            data["fingerprint"] = {
                "fingerprint_id": self.fingerprint.fingerprint_id,
                "stacks": self.fingerprint.stacks,
                "frameworks": self.fingerprint.frameworks,
            }

        if self.rules_dir:
            data["rules_dir"] = str(self.rules_dir)

        return data


class ProjectInitializer:
    """
    Initializes ProcessOS in a project directory.

    Creates (v0.8.0+):
    - .processos/config.yaml (unified config)
    - .processos/claude/ (instructions)

    Legacy format (v0.7.0):
    - .processos/fingerprint.yaml
    - .processos/binding.yaml
    - .processos/claude-rules/
    """

    def __init__(self, project_root: Path, use_unified_config: bool = True):
        """
        Initialize.

        Args:
            project_root: Path to project root
            use_unified_config: Use unified config.yaml format (v0.8.0+)
        """
        self.project_root = Path(project_root).resolve()
        self.manager = BindingManager(self.project_root)
        self.config_manager = ConfigManager(self.project_root)
        self.use_unified_config = use_unified_config

    def init(
        self,
        force: bool = False,
        project_name: Optional[str] = None,
        pillars: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
        skip_detect: bool = False,
        stack: Optional[str] = None,
    ) -> InitOutput:
        """
        Initialize ProcessOS in the project.

        Args:
            force: Overwrite existing binding if present
            project_name: Optional project name
            pillars: Optional list of active pillars
            timestamp: Optional fixed timestamp for determinism
            skip_detect: Skip auto-detection, use manual stack (T022)
            stack: Manual stack specification when skip_detect=True

        Returns:
            InitOutput with result and generated files
        """
        # Check for existing config (unified or legacy)
        if self.config_manager.is_initialized and not force:
            existing_config = self.config_manager.load()
            if existing_config:
                return InitOutput(
                    result=InitResult.ALREADY_EXISTS,
                    config=existing_config,
                    message="Project already initialized. Use --force to reinitialize.",
                )

        try:
            # Use unified config format (v0.8.0+)
            if self.use_unified_config:
                return self._init_unified(
                    project_name=project_name,
                    pillars=pillars,
                    skip_detect=skip_detect,
                    stack=stack,
                )
            else:
                return self._init_legacy(
                    project_name=project_name,
                    pillars=pillars,
                    timestamp=timestamp,
                )

        except Exception as e:
            return InitOutput(
                result=InitResult.WRITE_ERROR,
                message=f"Failed to initialize: {e}",
            )

    def _init_unified(
        self,
        project_name: Optional[str] = None,
        pillars: Optional[List[str]] = None,
        skip_detect: bool = False,
        stack: Optional[str] = None,
    ) -> InitOutput:
        """Initialize using unified config.yaml format (T020)."""
        stacks: List[StackConfig] = []
        frameworks: List[FrameworkConfig] = []
        fingerprint = None
        fingerprint_details = None

        if not skip_detect:
            # Auto-detect stack with detailed version extraction
            fingerprint_gen = FingerprintGenerator()
            fingerprint = fingerprint_gen.generate(self.project_root, include_details=True)

            # Convert to new format
            for s in fingerprint.stacks:
                stacks.append(StackConfig(
                    stack_id=s["stack_id"],
                    confidence=s["confidence"],
                    version_hint=s.get("version_hint"),
                ))

            for f in fingerprint.frameworks:
                frameworks.append(FrameworkConfig(
                    framework_id=f["framework_id"],
                    stack=f["stack"],
                    confidence=f["confidence"],
                ))

            # Get detailed version info
            fingerprint_details = fingerprint.details
        elif stack:
            # Manual stack specification
            stacks.append(StackConfig(
                stack_id=stack,
                confidence="high",  # Manual = high confidence
            ))

        # Create unified config with detailed fingerprint
        config = self.config_manager.create(
            project_name=project_name,
            stacks=stacks,
            frameworks=frameworks,
            pillars=pillars,
            fingerprint_details=fingerprint_details,
        )

        # Save config
        self.config_manager.save(config)

        # Get claude directory path (renamed from claude-rules)
        rules_dir = self.config_manager.get_claude_dir()

        return InitOutput(
            result=InitResult.SUCCESS,
            config=config,
            fingerprint=fingerprint,
            rules_dir=rules_dir,
            message=f"Initialized ProcessOS in {self.project_root}",
        )

    def _init_legacy(
        self,
        project_name: Optional[str] = None,
        pillars: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ) -> InitOutput:
        """Initialize using legacy binding.yaml + fingerprint.yaml format."""
        # Generate fingerprint
        fingerprint_gen = FingerprintGenerator()
        fingerprint = fingerprint_gen.generate(
            self.project_root,
            timestamp=timestamp,
        )

        # Generate binding
        binding_gen = BindingGenerator()
        binding = binding_gen.generate(
            fingerprint=fingerprint,
            project_name=project_name,
            pillars=pillars,
            timestamp=timestamp,
        )

        # Save files
        self.manager.save_fingerprint(fingerprint)
        self.manager.save_binding(binding)

        # Get rules directory path (will be populated by rules generator)
        rules_dir = self.manager.get_rules_dir()

        return InitOutput(
            result=InitResult.SUCCESS,
            binding=binding,
            fingerprint=fingerprint,
            rules_dir=rules_dir,
            message=f"Initialized ProcessOS in {self.project_root}",
        )

    def status(self) -> InitOutput:
        """
        Get current initialization status (T023).

        Returns:
            InitOutput with current state
        """
        # Try unified config first
        config = self.config_manager.load()
        if config:
            return InitOutput(
                result=InitResult.SUCCESS,
                config=config,
                rules_dir=self.config_manager.get_claude_dir(),
                message=f"Project initialized as '{config.project_name}'",
            )

        # Fall back to legacy format
        if not self.manager.exists():
            return InitOutput(
                result=InitResult.DETECTION_FAILED,
                message="Project not initialized. Run 'processos init' first.",
            )

        binding = self.manager.load_binding()
        fingerprint = self.manager.load_fingerprint()

        return InitOutput(
            result=InitResult.SUCCESS,
            binding=binding,
            fingerprint=fingerprint,
            rules_dir=self.manager.get_rules_dir(),
            message=f"Project initialized as '{binding.project_name}'",
        )

    def refresh_fingerprint(
        self,
        timestamp: Optional[str] = None,
    ) -> InitOutput:
        """
        Re-run fingerprint detection without full reinit.

        Args:
            timestamp: Optional fixed timestamp

        Returns:
            InitOutput with updated fingerprint
        """
        if not self.manager.exists():
            return InitOutput(
                result=InitResult.DETECTION_FAILED,
                message="Project not initialized. Run 'processos init' first.",
            )

        try:
            # Load existing binding
            binding = self.manager.load_binding()

            # Generate new fingerprint
            fingerprint_gen = FingerprintGenerator()
            fingerprint = fingerprint_gen.generate(
                self.project_root,
                timestamp=timestamp,
            )

            # Update binding's fingerprint ref
            binding_gen = BindingGenerator()
            new_binding = binding_gen.generate(
                fingerprint=fingerprint,
                project_name=binding.project_name,
                pillars=binding.pillars,
                timestamp=timestamp,
            )

            # Save updated files
            self.manager.save_fingerprint(fingerprint)
            self.manager.save_binding(new_binding)

            return InitOutput(
                result=InitResult.SUCCESS,
                binding=new_binding,
                fingerprint=fingerprint,
                rules_dir=self.manager.get_rules_dir(),
                message=f"Fingerprint refreshed: {fingerprint.fingerprint_id}",
            )

        except Exception as e:
            return InitOutput(
                result=InitResult.WRITE_ERROR,
                message=f"Failed to refresh fingerprint: {e}",
            )


def init_project(
    project_root: Path,
    force: bool = False,
    project_name: Optional[str] = None,
    pillars: Optional[List[str]] = None,
    timestamp: Optional[str] = None,
    skip_detect: bool = False,
    stack: Optional[str] = None,
    use_unified_config: bool = True,
) -> InitOutput:
    """
    Convenience function to initialize a project.

    Args:
        project_root: Path to project root
        force: Overwrite existing binding
        project_name: Optional project name
        pillars: Optional active pillars
        timestamp: Optional fixed timestamp
        skip_detect: Skip auto-detection (T022)
        stack: Manual stack specification
        use_unified_config: Use unified config.yaml (v0.8.0+)

    Returns:
        InitOutput
    """
    initializer = ProjectInitializer(project_root, use_unified_config=use_unified_config)
    return initializer.init(
        force=force,
        project_name=project_name,
        pillars=pillars,
        timestamp=timestamp,
        skip_detect=skip_detect,
        stack=stack,
    )
