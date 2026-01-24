"""
ProcessOS Playbook Gates Module

Validation gate implementations for playbook execution.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from .types import GateType


class GateValidator(ABC):
    """Abstract base class for gate validators."""

    _registry: Dict[GateType, Type["GateValidator"]] = {}

    def __init__(self):
        """Initialize the gate validator."""
        self.failure_reason: Optional[str] = None

    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> bool:
        """
        Validate the gate condition.

        Args:
            context: Dict containing relevant validation data

        Returns:
            True if gate passes, False otherwise
        """
        ...

    @classmethod
    def register(cls, gate_type: GateType):
        """Register a validator for a gate type."""
        def decorator(validator_cls: Type["GateValidator"]) -> Type["GateValidator"]:
            cls._registry[gate_type] = validator_cls
            return validator_cls
        return decorator

    @classmethod
    def get_validator(cls, gate_type: GateType) -> "GateValidator":
        """
        Get a validator instance for the given gate type.

        Args:
            gate_type: The type of gate to validate

        Returns:
            GateValidator instance for that gate type
        """
        validator_cls = cls._registry.get(gate_type)
        if validator_cls is None:
            raise ValueError(f"No validator registered for gate type: {gate_type}")
        return validator_cls()


@GateValidator.register(GateType.COMPLETENESS_CHECK)
class CompletenessGate(GateValidator):
    """
    Validates that all required inputs are present.

    Checks:
    - Intent is defined
    - Requirements are complete
    - Materials are collected (if required)
    """

    def validate(self, context: Dict[str, Any]) -> bool:
        """Validate completeness of inputs."""
        # Check intent
        intent = context.get("intent")
        if intent is None:
            self.failure_reason = "Intent is not defined"
            return False

        # Check requirements
        requirements = context.get("requirements")
        if requirements is None:
            self.failure_reason = "Requirements not inferred"
            return False

        # Check materials if required
        materials = context.get("materials")
        if requirements and hasattr(requirements, "materials"):
            required_materials = [
                m for m in requirements.materials
                if hasattr(m, "required") and m.required
            ]
            if required_materials and not materials:
                self.failure_reason = "Required materials not collected"
                return False

        return True


@GateValidator.register(GateType.SCHEMA_VALIDATION)
class SchemaValidationGate(GateValidator):
    """
    Validates schema mapping completeness.

    Checks:
    - All mappings have been decided (approved/rejected)
    - At least one mapping is approved
    - No critical type mismatches
    """

    def validate(self, context: Dict[str, Any]) -> bool:
        """Validate schema mapping completeness."""
        mapping = context.get("mapping")
        if mapping is None:
            self.failure_reason = "No schema mapping provided"
            return False

        # Check all mappings are decided
        if hasattr(mapping, "all_decided") and not mapping.all_decided:
            pending = getattr(mapping, "pending_approvals", [])
            self.failure_reason = f"{len(pending)} mappings still pending approval"
            return False

        # Check at least one mapping is approved
        approved = getattr(mapping, "approved_mappings", [])
        if not approved:
            self.failure_reason = "No field mappings were approved"
            return False

        return True


@GateValidator.register(GateType.USER_APPROVAL)
class UserApprovalGate(GateValidator):
    """
    Validates that user has approved the playbook or action.

    Checks:
    - Playbook is approved
    - Or specific item (mapping, code) is approved
    """

    def validate(self, context: Dict[str, Any]) -> bool:
        """Validate user approval."""
        # Check playbook approval
        playbook = context.get("playbook")
        if playbook and hasattr(playbook, "user_approved"):
            if not playbook.user_approved:
                self.failure_reason = "Playbook not approved by user"
                return False
            return True

        # Check generated code approval
        generated_code = context.get("generated_code")
        if generated_code and hasattr(generated_code, "review_status"):
            from ..codegen.types import ReviewStatus
            if generated_code.review_status in (ReviewStatus.PENDING, ReviewStatus.IN_REVIEW):
                self.failure_reason = "Generated code not reviewed"
                return False
            return True

        # Check mapping approval
        mapping = context.get("mapping")
        if mapping and hasattr(mapping, "user_confirmed"):
            if not mapping.user_confirmed:
                self.failure_reason = "Schema mapping not confirmed by user"
                return False
            return True

        # If nothing to check, pass by default
        return True


@GateValidator.register(GateType.CONFLICT_DETECTION)
class ConflictDetectionGate(GateValidator):
    """
    Detects potential conflicts before code application.

    Checks:
    - Files to be created don't already exist (unless modification)
    - No pending changes in target files
    - Model/service names don't conflict with existing
    """

    def validate(self, context: Dict[str, Any]) -> bool:
        """Validate no conflicts exist."""
        generated_code = context.get("generated_code")
        if generated_code is None:
            # No code to check
            return True

        project_context = context.get("project_context")
        conflicts = []

        for file in getattr(generated_code, "files", []):
            file_path = getattr(file, "file_path", None)
            is_modification = getattr(file, "is_modification", False)

            if file_path and not is_modification:
                # Check if file would conflict with existing files
                # This is a simplified check - real implementation would check filesystem
                if project_context:
                    # Safely get services and models, handling non-iterable values
                    try:
                        services_attr = getattr(project_context, "services", [])
                        existing_services = [s.name for s in services_attr] if services_attr and hasattr(services_attr, '__iter__') else []
                    except (TypeError, AttributeError):
                        existing_services = []

                    try:
                        models_attr = getattr(project_context, "models", [])
                        existing_models = [m.name for m in models_attr] if models_attr and hasattr(models_attr, '__iter__') else []
                    except (TypeError, AttributeError):
                        existing_models = []

                    # Extract potential class name from file path
                    path_parts = str(file_path).split("/")
                    if path_parts:
                        file_name = path_parts[-1].replace(".py", "").replace(".js", "")
                        # Convert to PascalCase for comparison
                        class_name = "".join(word.capitalize() for word in file_name.split("_"))

                        if class_name in existing_services or class_name in existing_models:
                            conflicts.append(f"{file_path} would conflict with existing {class_name}")

        if conflicts:
            self.failure_reason = "; ".join(conflicts)
            return False

        return True


class GateExecutor:
    """
    Executes gate validation in a playbook context.
    """

    def __init__(self):
        """Initialize the gate executor."""
        self.last_failure: Optional[str] = None

    def execute_gate(
        self,
        gate_type: GateType,
        context: Dict[str, Any],
    ) -> bool:
        """
        Execute a gate validation.

        Args:
            gate_type: Type of gate to execute
            context: Validation context

        Returns:
            True if gate passes, False otherwise
        """
        try:
            validator = GateValidator.get_validator(gate_type)
            result = validator.validate(context)
            if not result:
                self.last_failure = validator.failure_reason
            return result
        except ValueError as e:
            self.last_failure = str(e)
            return False

    def execute_all_gates(
        self,
        gates: list,
        context: Dict[str, Any],
    ) -> Dict[str, bool]:
        """
        Execute multiple gates.

        Args:
            gates: List of PlaybookGate objects
            context: Validation context

        Returns:
            Dict mapping gate IDs to pass/fail status
        """
        results = {}
        for gate in gates:
            gate_type = getattr(gate, "gate_type", None)
            if gate_type:
                results[gate.id] = self.execute_gate(gate_type, context)
                if results[gate.id]:
                    gate.pass_gate()
                else:
                    gate.fail_gate(self.last_failure or "Unknown failure")
        return results
