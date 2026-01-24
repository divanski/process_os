"""
ProcessOS - AI Agent Squad Orchestration Framework

Programmatic API entry point for integrating ProcessOS into your applications (T055).

Usage:
    from process_os import init_project, execute_command, get_status

    # Initialize a project
    result = init_project("./my-project")

    # Execute a command
    output = execute_command("./my-project", "integrate courier DHL")

    # Check status
    status = get_status("./my-project")
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from process_os.bootstrap import CommandGateway
from process_os.init import (
    PROCESSOS_DIR,
    PROCESSOS_VERSION,
    ConfigManager,
    InitOutput,
    InitResult,
    ProjectConfig,
    ProjectInitializer,
)
from process_os.init.binding import (
    get_global_config_path,
    get_processos_home,
    get_team_config_path,
)
from process_os.init.initializer import (
    detect_ci_environment,
    is_ci_environment,
)

__version__ = PROCESSOS_VERSION
__all__ = [
    # Version
    "__version__",
    "PROCESSOS_VERSION",
    "PROCESSOS_DIR",
    # Core functions
    "init_project",
    "get_status",
    "execute_command",
    "get_config",
    "update_config",
    "validate_config",
    # Classes
    "ProjectConfig",
    "ConfigManager",
    "InitOutput",
    "InitResult",
    # Utilities
    "is_ci_environment",
    "detect_ci_environment",
    "get_processos_home",
    "get_global_config_path",
    "get_team_config_path",
]


def init_project(
    project_root: str,
    force: bool = False,
    project_name: Optional[str] = None,
    pillars: Optional[List[str]] = None,
    skip_detect: bool = False,
    stack: Optional[str] = None,
) -> InitOutput:
    """
    Initialize ProcessOS in a project directory.

    Args:
        project_root: Path to project root directory
        force: Overwrite existing initialization
        project_name: Optional project name (defaults to directory name)
        pillars: Optional list of pillars to activate
        skip_detect: Skip auto-detection of stack
        stack: Manual stack specification (when skip_detect=True)

    Returns:
        InitOutput with result and configuration

    Example:
        >>> from process_os import init_project
        >>> result = init_project("./my-project")
        >>> print(result.config.project_name)
        'my-project'
    """
    initializer = ProjectInitializer(Path(project_root))
    return initializer.init(
        force=force,
        project_name=project_name,
        pillars=pillars,
        skip_detect=skip_detect,
        stack=stack,
    )


def get_status(project_root: str) -> InitOutput:
    """
    Get ProcessOS status for a project.

    Args:
        project_root: Path to project root directory

    Returns:
        InitOutput with current configuration

    Example:
        >>> from process_os import get_status
        >>> status = get_status("./my-project")
        >>> if status.result == InitResult.SUCCESS:
        ...     print(f"Project: {status.config.project_name}")
    """
    initializer = ProjectInitializer(Path(project_root))
    return initializer.status()


def execute_command(
    project_root: str,
    command: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute a command through the ProcessOS gateway.

    Args:
        project_root: Path to project root directory
        command: Command to execute (e.g., "integrate courier DHL")
        dry_run: Preview without executing

    Returns:
        Dictionary with execution result

    Example:
        >>> from process_os import execute_command
        >>> result = execute_command("./my-project", "integrate courier DHL")
        >>> print(result["workspace_id"])
    """
    gateway = CommandGateway(Path(project_root))
    result = gateway.execute(command, dry_run=dry_run)
    return result.to_dict()


def get_config(project_root: str) -> Optional[ProjectConfig]:
    """
    Get project configuration.

    Args:
        project_root: Path to project root directory

    Returns:
        ProjectConfig if initialized, None otherwise

    Example:
        >>> from process_os import get_config
        >>> config = get_config("./my-project")
        >>> if config:
        ...     print(config.stacks)
    """
    manager = ConfigManager(Path(project_root))
    return manager.load()


def update_config(project_root: str, path: str, value: Any) -> ProjectConfig:
    """
    Update a configuration setting.

    Args:
        project_root: Path to project root directory
        path: Dot-separated path (e.g., "settings.observability.mode")
        value: New value

    Returns:
        Updated ProjectConfig

    Example:
        >>> from process_os import update_config
        >>> config = update_config("./my-project", "settings.observability.mode", "full")
    """
    manager = ConfigManager(Path(project_root))
    return manager.update_setting(path, value)


def validate_config(project_root: str, fix: bool = False) -> Dict[str, Any]:
    """
    Validate project configuration.

    Args:
        project_root: Path to project root directory
        fix: Automatically fix fixable issues

    Returns:
        Dictionary with validation result

    Example:
        >>> from process_os import validate_config
        >>> result = validate_config("./my-project", fix=True)
        >>> if result["valid"]:
        ...     print("Configuration is valid")
    """
    manager = ConfigManager(Path(project_root))
    result = manager.validate(fix=fix)
    return result.to_dict()
