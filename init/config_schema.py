"""
ProcessOS Config Schema Validation

Validates ProjectConfig YAML files against the defined schema.
Provides detailed error messages with remediation suggestions.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationSeverity(Enum):
    """Severity level for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue found in the config."""
    path: str  # JSON path to the issue (e.g., "fingerprint.stacks[0].confidence")
    message: str
    severity: ValidationSeverity
    remediation: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of config validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


# Schema constants
CONFIG_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
BINDING_ID_PATTERN = r"^bind-[a-f0-9]{12}$"
FINGERPRINT_ID_PATTERN = r"^fp-[a-f0-9]{12}$"
VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
VALID_OBSERVABILITY_MODES = {"minimal", "full", "silent"}
VALID_CREDENTIAL_SOURCES = {"env", "keychain", "file"}


class ConfigSchemaValidator:
    """Validates ProcessOS config.yaml files."""

    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate a config dictionary against the schema.

        Args:
            config: Parsed YAML config dictionary

        Returns:
            ValidationResult with is_valid flag and any issues found
        """
        issues: List[ValidationIssue] = []

        # Required top-level fields
        issues.extend(self._validate_version(config))
        issues.extend(self._validate_project(config))
        issues.extend(self._validate_binding(config))
        issues.extend(self._validate_fingerprint(config))
        issues.extend(self._validate_settings(config))

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return ValidationResult(is_valid=is_valid, issues=issues)

    def _validate_version(self, config: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate version field."""
        issues = []
        version = config.get("version")

        if version is None:
            issues.append(ValidationIssue(
                path="version",
                message="Missing required field 'version'",
                severity=ValidationSeverity.ERROR,
                remediation="Add 'version: \"1.0.0\"' to your config.yaml"
            ))
        elif not isinstance(version, str):
            issues.append(ValidationIssue(
                path="version",
                message=f"Version must be a string, got {type(version).__name__}",
                severity=ValidationSeverity.ERROR,
                remediation="Change version to a string like \"1.0.0\""
            ))
        elif not re.match(CONFIG_VERSION_PATTERN, version):
            issues.append(ValidationIssue(
                path="version",
                message=f"Version '{version}' does not follow semver format",
                severity=ValidationSeverity.ERROR,
                remediation="Use semantic versioning format: \"MAJOR.MINOR.PATCH\" (e.g., \"1.0.0\")"
            ))

        return issues

    def _validate_project(self, config: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate project section."""
        issues = []
        project = config.get("project")

        if project is None:
            issues.append(ValidationIssue(
                path="project",
                message="Missing required section 'project'",
                severity=ValidationSeverity.ERROR,
                remediation="Add a 'project:' section with 'name' and 'root' fields"
            ))
            return issues

        if not isinstance(project, dict):
            issues.append(ValidationIssue(
                path="project",
                message="Project must be a mapping",
                severity=ValidationSeverity.ERROR,
                remediation="Structure 'project:' as a YAML mapping with 'name' and 'root'"
            ))
            return issues

        if not project.get("name"):
            issues.append(ValidationIssue(
                path="project.name",
                message="Missing required field 'project.name'",
                severity=ValidationSeverity.ERROR,
                remediation="Add 'name: \"your-project-name\"' under 'project:'"
            ))

        return issues

    def _validate_binding(self, config: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate binding section."""
        issues = []
        binding = config.get("binding")

        if binding is None:
            issues.append(ValidationIssue(
                path="binding",
                message="Missing required section 'binding'",
                severity=ValidationSeverity.ERROR,
                remediation="Add a 'binding:' section with 'binding_id' and 'processos_version'"
            ))
            return issues

        if not isinstance(binding, dict):
            issues.append(ValidationIssue(
                path="binding",
                message="Binding must be a mapping",
                severity=ValidationSeverity.ERROR,
                remediation="Structure 'binding:' as a YAML mapping"
            ))
            return issues

        binding_id = binding.get("binding_id")
        if binding_id and not re.match(BINDING_ID_PATTERN, binding_id):
            issues.append(ValidationIssue(
                path="binding.binding_id",
                message=f"Invalid binding_id format: '{binding_id}'",
                severity=ValidationSeverity.ERROR,
                remediation="Binding ID must match pattern 'bind-' followed by 12 hex characters"
            ))

        return issues

    def _validate_fingerprint(self, config: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate fingerprint section."""
        issues = []
        fingerprint = config.get("fingerprint")

        if fingerprint is None:
            issues.append(ValidationIssue(
                path="fingerprint",
                message="Missing required section 'fingerprint'",
                severity=ValidationSeverity.WARNING,
                remediation="Run 'processos init' to generate fingerprint automatically"
            ))
            return issues

        if not isinstance(fingerprint, dict):
            issues.append(ValidationIssue(
                path="fingerprint",
                message="Fingerprint must be a mapping",
                severity=ValidationSeverity.ERROR,
                remediation="Structure 'fingerprint:' as a YAML mapping"
            ))
            return issues

        fp_id = fingerprint.get("fingerprint_id")
        if fp_id and not re.match(FINGERPRINT_ID_PATTERN, fp_id):
            issues.append(ValidationIssue(
                path="fingerprint.fingerprint_id",
                message=f"Invalid fingerprint_id format: '{fp_id}'",
                severity=ValidationSeverity.ERROR,
                remediation="Fingerprint ID must match pattern 'fp-' followed by 12 hex characters"
            ))

        # Validate stacks
        stacks = fingerprint.get("stacks", [])
        if isinstance(stacks, list):
            for i, stack in enumerate(stacks):
                if isinstance(stack, dict):
                    confidence = stack.get("confidence")
                    if confidence and confidence not in VALID_CONFIDENCE_LEVELS:
                        issues.append(ValidationIssue(
                            path=f"fingerprint.stacks[{i}].confidence",
                            message=f"Invalid confidence level: '{confidence}'",
                            severity=ValidationSeverity.ERROR,
                            remediation=f"Use one of: {', '.join(VALID_CONFIDENCE_LEVELS)}"
                        ))

        # Validate frameworks
        frameworks = fingerprint.get("frameworks", [])
        if isinstance(frameworks, list):
            for i, framework in enumerate(frameworks):
                if isinstance(framework, dict):
                    confidence = framework.get("confidence")
                    if confidence and confidence not in VALID_CONFIDENCE_LEVELS:
                        issues.append(ValidationIssue(
                            path=f"fingerprint.frameworks[{i}].confidence",
                            message=f"Invalid confidence level: '{confidence}'",
                            severity=ValidationSeverity.ERROR,
                            remediation=f"Use one of: {', '.join(VALID_CONFIDENCE_LEVELS)}"
                        ))

        return issues

    def _validate_settings(self, config: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate settings section."""
        issues = []
        settings = config.get("settings")

        if settings is None:
            # Settings are optional
            return issues

        if not isinstance(settings, dict):
            issues.append(ValidationIssue(
                path="settings",
                message="Settings must be a mapping",
                severity=ValidationSeverity.ERROR,
                remediation="Structure 'settings:' as a YAML mapping"
            ))
            return issues

        # Validate observability
        observability = settings.get("observability", {})
        if isinstance(observability, dict):
            mode = observability.get("mode")
            if mode and mode not in VALID_OBSERVABILITY_MODES:
                issues.append(ValidationIssue(
                    path="settings.observability.mode",
                    message=f"Invalid observability mode: '{mode}'",
                    severity=ValidationSeverity.ERROR,
                    remediation=f"Use one of: {', '.join(VALID_OBSERVABILITY_MODES)}"
                ))

        # Validate credentials
        credentials = settings.get("credentials", {})
        if isinstance(credentials, dict):
            sources = credentials.get("sources", [])
            if isinstance(sources, list):
                for i, source in enumerate(sources):
                    if source not in VALID_CREDENTIAL_SOURCES:
                        issues.append(ValidationIssue(
                            path=f"settings.credentials.sources[{i}]",
                            message=f"Invalid credential source: '{source}'",
                            severity=ValidationSeverity.ERROR,
                            remediation=f"Use one of: {', '.join(VALID_CREDENTIAL_SOURCES)}"
                        ))

        return issues


def validate_config(config: Dict[str, Any]) -> ValidationResult:
    """
    Convenience function to validate a config dictionary.

    Args:
        config: Parsed YAML config dictionary

    Returns:
        ValidationResult with validation status and any issues
    """
    validator = ConfigSchemaValidator()
    return validator.validate(config)
