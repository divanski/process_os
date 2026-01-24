"""
ProcessOS Playbook Builder Module

Dynamically generates playbooks based on intent and requirements.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .types import (
    DynamicPlaybook,
    GateType,
    PlaybookGate,
    PlaybookStep,
    StepStatus,
    StepType,
)
from .gates import GateExecutor

if TYPE_CHECKING:
    from ..discovery import ProjectContext
    from ..intent import Intent
    from ..requirements import Requirements


# Step templates for different integration types
INTEGRATION_STEP_TEMPLATES = {
    "supplier_api": [
        StepType.DISCOVERY,
        StepType.INTENT_ANALYSIS,
        StepType.MATERIAL_COLLECTION,
        StepType.SCHEMA_MAPPING,
        StepType.USER_CONFIRMATION,
        StepType.CODE_GENERATION,
        StepType.CODE_REVIEW,
        StepType.CODE_APPLICATION,
    ],
    "payment": [
        StepType.DISCOVERY,
        StepType.INTENT_ANALYSIS,
        StepType.MATERIAL_COLLECTION,
        StepType.SCHEMA_MAPPING,
        StepType.USER_CONFIRMATION,
        StepType.CODE_GENERATION,
        StepType.CODE_REVIEW,
        StepType.CODE_APPLICATION,
    ],
    "notification": [
        StepType.DISCOVERY,
        StepType.INTENT_ANALYSIS,
        StepType.MATERIAL_COLLECTION,
        StepType.CODE_GENERATION,
        StepType.CODE_REVIEW,
        StepType.CODE_APPLICATION,
    ],
    "default": [
        StepType.DISCOVERY,
        StepType.INTENT_ANALYSIS,
        StepType.REQUIREMENTS_GATHER,
        StepType.MATERIAL_COLLECTION,
        StepType.CODE_GENERATION,
        StepType.CODE_REVIEW,
        StepType.CODE_APPLICATION,
    ],
}

# Gate placement rules
GATE_RULES = {
    StepType.SCHEMA_MAPPING: [GateType.SCHEMA_VALIDATION, GateType.USER_APPROVAL],
    StepType.CODE_GENERATION: [GateType.COMPLETENESS_CHECK],
    StepType.CODE_REVIEW: [GateType.USER_APPROVAL, GateType.CONFLICT_DETECTION],
}

# Step metadata
STEP_METADATA = {
    StepType.DISCOVERY: {
        "name": "Project Discovery",
        "description": "Analyze project structure, models, routes, and conventions",
    },
    StepType.INTENT_ANALYSIS: {
        "name": "Intent Analysis",
        "description": "Parse and understand the integration request",
    },
    StepType.REQUIREMENTS_GATHER: {
        "name": "Requirements Gathering",
        "description": "Infer required materials and decisions",
    },
    StepType.MATERIAL_COLLECTION: {
        "name": "Material Collection",
        "description": "Collect API documentation, credentials, and other materials",
    },
    StepType.SCHEMA_MAPPING: {
        "name": "Schema Mapping",
        "description": "Map external API schemas to local models",
    },
    StepType.USER_CONFIRMATION: {
        "name": "User Confirmation",
        "description": "Review and confirm integration details",
    },
    StepType.CODE_GENERATION: {
        "name": "Code Generation",
        "description": "Generate integration code following project conventions",
    },
    StepType.CODE_REVIEW: {
        "name": "Code Review",
        "description": "Review generated code and approve changes",
    },
    StepType.CODE_APPLICATION: {
        "name": "Code Application",
        "description": "Apply generated code to the project",
    },
}


class PlaybookBuilder:
    """
    Dynamically builds playbooks based on intent and requirements.

    Features:
    - Integration type-specific step templates
    - Automatic dependency ordering
    - Gate generation based on step types
    - Context-aware step customization
    """

    def __init__(
        self,
        project_context: Optional["ProjectContext"] = None,
    ):
        """
        Initialize the playbook builder.

        Args:
            project_context: Optional project context for customization
        """
        self.project_context = project_context
        self.gate_executor = GateExecutor()

    def build(
        self,
        intent: "Intent",
        requirements: "Requirements",
    ) -> DynamicPlaybook:
        """
        Build a dynamic playbook for the integration.

        Args:
            intent: Parsed user intent
            requirements: Inferred requirements

        Returns:
            DynamicPlaybook with steps and gates
        """
        playbook_id = str(uuid.uuid4())[:8]

        # Get integration type
        integration_type = getattr(intent, "integration_type", "default")
        integration_name = getattr(intent, "target_service", None) or integration_type

        # Generate intent ID from integration type and target (Intent doesn't have id field)
        intent_id = f"{integration_type}_{integration_name}".replace(" ", "_").lower()

        # Create playbook
        playbook = DynamicPlaybook(
            id=playbook_id,
            intent_id=intent_id,
            name=f"{self._format_name(integration_name)} Integration",
            description=f"Dynamic playbook for {integration_type}: {integration_name}",
        )

        # Generate steps
        steps = self._generate_steps(integration_type, intent, requirements)
        playbook.steps = steps

        # Generate gates
        gates = self._generate_gates(steps)
        playbook.gates = gates

        return playbook

    def _generate_steps(
        self,
        integration_type: str,
        intent: "Intent",
        requirements: "Requirements",
    ) -> List[PlaybookStep]:
        """
        Generate steps for the playbook.

        Args:
            integration_type: Type of integration
            intent: User intent
            requirements: Inferred requirements

        Returns:
            List of PlaybookStep objects
        """
        # Get step template for integration type
        step_types = INTEGRATION_STEP_TEMPLATES.get(
            integration_type,
            INTEGRATION_STEP_TEMPLATES["default"]
        )

        # Customize steps based on requirements
        step_types = self._customize_steps(step_types, requirements)

        # Build step objects
        steps = []
        prev_step_id = None

        for i, step_type in enumerate(step_types):
            step_id = f"step_{i + 1:03d}"
            metadata = STEP_METADATA.get(step_type, {
                "name": step_type.value.replace("_", " ").title(),
                "description": f"Execute {step_type.value}",
            })

            step = PlaybookStep(
                id=step_id,
                name=metadata["name"],
                description=metadata["description"],
                step_type=step_type,
                depends_on=[prev_step_id] if prev_step_id else [],
            )
            steps.append(step)
            prev_step_id = step_id

        return steps

    def _customize_steps(
        self,
        step_types: List[StepType],
        requirements: "Requirements",
    ) -> List[StepType]:
        """
        Customize steps based on requirements.

        Args:
            step_types: Initial step types
            requirements: Inferred requirements

        Returns:
            Customized list of step types
        """
        # Check if materials are required
        materials = getattr(requirements, "materials", [])
        has_api_docs = any(
            getattr(m, "type", "") == "api_documentation"
            for m in materials
        )

        # If no API docs, may not need schema mapping
        if not has_api_docs and StepType.SCHEMA_MAPPING in step_types:
            # Keep schema mapping but it will be optional
            pass

        # Check for decisions that require user confirmation
        decisions = getattr(requirements, "decisions", [])
        if decisions and StepType.USER_CONFIRMATION not in step_types:
            # Insert user confirmation before code generation
            try:
                codegen_idx = step_types.index(StepType.CODE_GENERATION)
                step_types = (
                    step_types[:codegen_idx] +
                    [StepType.USER_CONFIRMATION] +
                    step_types[codegen_idx:]
                )
            except ValueError:
                pass

        return step_types

    def _generate_gates(
        self,
        steps: List[PlaybookStep],
    ) -> List[PlaybookGate]:
        """
        Generate gates for the playbook.

        Args:
            steps: Playbook steps

        Returns:
            List of PlaybookGate objects
        """
        gates = []
        gate_counter = 0

        for step in steps:
            gate_types = GATE_RULES.get(step.step_type, [])

            for gate_type in gate_types:
                gate_counter += 1
                gate = PlaybookGate(
                    id=f"gate_{gate_counter:03d}",
                    name=self._format_gate_name(gate_type),
                    gate_type=gate_type,
                    after_step=step.id,
                    validation_rules=self._get_validation_rules(gate_type),
                )
                gates.append(gate)

        return gates

    def _format_name(self, name: str) -> str:
        """Format a name to PascalCase."""
        words = name.replace("_", " ").replace("-", " ").split()
        return "".join(word.capitalize() for word in words)

    def _format_gate_name(self, gate_type: GateType) -> str:
        """Format a gate type to a readable name."""
        return gate_type.value.replace("_", " ").title()

    def _get_validation_rules(self, gate_type: GateType) -> List[str]:
        """Get validation rules for a gate type."""
        rules = {
            GateType.SCHEMA_VALIDATION: [
                "All field mappings must be decided",
                "At least one mapping must be approved",
                "No critical type mismatches",
            ],
            GateType.USER_APPROVAL: [
                "User must explicitly approve",
            ],
            GateType.COMPLETENESS_CHECK: [
                "Intent must be defined",
                "Requirements must be complete",
                "Required materials must be collected",
            ],
            GateType.CONFLICT_DETECTION: [
                "No file conflicts with existing code",
                "No uncommitted changes in target files",
            ],
        }
        return rules.get(gate_type, [])

    def execute_step(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """
        Execute a playbook step.

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            True if step completed successfully
        """
        step.start()

        try:
            # Route to appropriate handler based on step type
            handler = self._get_step_handler(step.step_type)
            if handler:
                result = handler(step, context)
                if result:
                    step.complete()
                    return True
                else:
                    step.block("Step handler returned False")
                    return False
            else:
                # No handler - step is manual
                step.block("Requires manual action")
                return False

        except Exception as e:
            step.fail(str(e))
            return False

    def _get_step_handler(self, step_type: StepType):
        """Get the handler function for a step type."""
        handlers = {
            StepType.DISCOVERY: self._handle_discovery,
            StepType.INTENT_ANALYSIS: self._handle_intent_analysis,
            StepType.REQUIREMENTS_GATHER: self._handle_requirements_gather,
            StepType.MATERIAL_COLLECTION: self._handle_material_collection,
            StepType.SCHEMA_MAPPING: self._handle_schema_mapping,
            StepType.CODE_GENERATION: self._handle_code_generation,
            StepType.CODE_REVIEW: self._handle_code_review,
            StepType.CODE_APPLICATION: self._handle_code_application,
        }
        return handlers.get(step_type)

    def _handle_discovery(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle discovery step."""
        # If project context already provided, discovery is done
        if self.project_context:
            context["project_context"] = self.project_context
            return True

        # Otherwise, needs external discovery
        project_root = context.get("project_root")
        if not project_root:
            step.block("No project root specified")
            return False

        # Discovery would be executed externally
        return False

    def _handle_intent_analysis(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle intent analysis step."""
        intent = context.get("intent")
        if intent:
            return True
        # Intent analysis would be done externally
        return False

    def _handle_requirements_gather(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle requirements gathering step."""
        requirements = context.get("requirements")
        if requirements:
            return True
        return False

    def _handle_material_collection(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle material collection step."""
        materials = context.get("materials")
        requirements = context.get("requirements")

        if not requirements:
            return True  # No requirements means no materials needed

        # Check if all required materials are collected
        required = [
            m for m in getattr(requirements, "materials", [])
            if getattr(m, "required", True)
        ]

        if not required:
            return True

        if materials:
            # Simplified check - real implementation would verify each material
            return True

        return False

    def _handle_schema_mapping(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle schema mapping step."""
        mapping = context.get("mapping")
        if mapping and getattr(mapping, "all_decided", False):
            return True
        return False

    def _handle_code_generation(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle code generation step."""
        generated_code = context.get("generated_code")
        if generated_code:
            return True
        return False

    def _handle_code_review(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle code review step."""
        generated_code = context.get("generated_code")
        if generated_code and getattr(generated_code, "all_decided", False):
            return True
        return False

    def _handle_code_application(
        self,
        step: PlaybookStep,
        context: Dict[str, Any],
    ) -> bool:
        """Handle code application step."""
        patchset = context.get("patchset")
        if patchset and getattr(patchset, "applied", False):
            return True
        return False

    def run_playbook(
        self,
        playbook: DynamicPlaybook,
        context: Dict[str, Any],
        auto_approve_gates: bool = False,
    ) -> bool:
        """
        Run a playbook to completion.

        Args:
            playbook: Playbook to execute
            context: Execution context
            auto_approve_gates: If True, auto-approve user approval gates

        Returns:
            True if playbook completed successfully
        """
        if not playbook.user_approved:
            raise ValueError("Playbook must be approved before execution")

        playbook.start_execution()

        while True:
            ready_steps = playbook.get_ready_steps()
            if not ready_steps:
                # Check if all steps are completed
                all_complete = all(
                    s.status == StepStatus.COMPLETED
                    for s in playbook.steps
                )
                if all_complete:
                    playbook.complete()
                    return True
                else:
                    playbook.block()
                    return False

            for step in ready_steps:
                # Execute step
                step_result = self.execute_step(step, context)

                if not step_result:
                    # Step blocked or failed
                    if step.status == StepStatus.FAILED:
                        playbook.fail()
                        return False
                    # Otherwise blocked - stop processing
                    playbook.block()
                    return False

                # Check gates after step
                gate = playbook.get_gate_after_step(step.id)
                if gate:
                    if gate.gate_type == GateType.USER_APPROVAL and auto_approve_gates:
                        gate.bypass()
                    else:
                        gate_result = self.gate_executor.execute_gate(
                            gate.gate_type,
                            context,
                        )
                        if gate_result:
                            gate.pass_gate()
                        else:
                            gate.fail_gate(
                                self.gate_executor.last_failure or "Gate validation failed"
                            )
                            playbook.block()
                            return False

        return False
