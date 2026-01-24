"""
ProcessOS Init Module

Project initialization and binding management.
"""

from .binding import (
    PROCESSOS_DIR,
    PROCESSOS_VERSION,
    BindingGenerator,
    BindingManager,
    ProjectBinding,
    generate_binding,
)
from .binding import (
    get_global_config_path,
    get_processos_home,
    get_team_config_path,
)
from .config import (
    CISettings,
    ConfigIssue,
    ConfigManager,
    ConfigValidationResult,
    CredentialSettings,
    FrameworkConfig,
    ObservabilitySettings,
    ProjectConfig,
    ProjectSettings,
    StackConfig,
    TeamConfig,
)
from .config_schema import (
    ConfigSchemaValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    validate_config,
)
from .initializer import (
    InitOutput,
    InitResult,
    ProjectInitializer,
    detect_ci_environment,
    init_project,
    is_ci_environment,
)
from .migration import (
    MigrationError,
    can_migrate,
    get_migration_status,
    migrate_to_unified_config,
    rollback_migration,
)

__all__ = [
    # Constants
    "PROCESSOS_DIR",
    "PROCESSOS_VERSION",
    # Binding (legacy)
    "ProjectBinding",
    "BindingGenerator",
    "BindingManager",
    "generate_binding",
    # Binding utilities (T054)
    "get_processos_home",
    "get_global_config_path",
    "get_team_config_path",
    # Config (v0.8.0+)
    "ProjectConfig",
    "ConfigManager",
    "StackConfig",
    "FrameworkConfig",
    "ProjectSettings",
    "ObservabilitySettings",
    "CredentialSettings",
    "CISettings",
    "TeamConfig",
    "ConfigIssue",
    "ConfigValidationResult",
    # Config Schema Validation
    "ConfigSchemaValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "validate_config",
    # Migration
    "migrate_to_unified_config",
    "can_migrate",
    "rollback_migration",
    "get_migration_status",
    "MigrationError",
    # Initializer
    "ProjectInitializer",
    "InitResult",
    "InitOutput",
    "init_project",
    # CI detection (T051)
    "is_ci_environment",
    "detect_ci_environment",
]
