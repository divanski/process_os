"""
ProcessOS Requirements Engine Module

Infers integration requirements from parsed intent.
Determines what materials (API docs, credentials) and decisions are needed.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
import uuid

from .types import (
    DecisionOption,
    DecisionRequirement,
    DecisionType,
    MaterialRequirement,
    MaterialType,
    Requirements,
)

if TYPE_CHECKING:
    from ..intent import Intent


# Default requirements by integration type
INTEGRATION_TYPE_REQUIREMENTS = {
    "supplier_api": {
        "materials": [
            {
                "type": MaterialType.API_DOCUMENTATION,
                "name": "API Documentation",
                "description": "OpenAPI/Swagger spec or manual endpoint documentation",
                "required": True,
            },
            {
                "type": MaterialType.CREDENTIAL_REFERENCE,
                "name": "API Credentials",
                "description": "Environment variable name for API key/token",
                "required": True,
            },
            {
                "type": MaterialType.EXAMPLE_REQUEST,
                "name": "Example Request",
                "description": "Sample API request for validation",
                "required": False,
            },
        ],
        "decisions": [
            {
                "type": DecisionType.ERROR_HANDLING,
                "question": "How should API errors be handled?",
                "options": [
                    {"id": "retry", "label": "Retry with backoff", "description": "Automatic retry with exponential backoff"},
                    {"id": "fail_fast", "label": "Fail immediately", "description": "Stop on first error, report to user"},
                    {"id": "skip", "label": "Skip and continue", "description": "Log error and continue with next item"},
                ],
                "default": "retry",
            },
        ],
    },
    "payment": {
        "materials": [
            {
                "type": MaterialType.API_DOCUMENTATION,
                "name": "Payment API Documentation",
                "description": "Payment gateway API documentation",
                "required": True,
            },
            {
                "type": MaterialType.CREDENTIAL_REFERENCE,
                "name": "Payment Credentials",
                "description": "Environment variable names for payment API keys",
                "required": True,
            },
        ],
        "decisions": [
            {
                "type": DecisionType.ERROR_HANDLING,
                "question": "How should payment failures be handled?",
                "options": [
                    {"id": "retry", "label": "Retry payment", "description": "Retry failed payments with backoff"},
                    {"id": "fail_notify", "label": "Fail and notify", "description": "Fail transaction and notify user"},
                    {"id": "queue", "label": "Queue for manual review", "description": "Queue failed payments for manual processing"},
                ],
                "default": "fail_notify",
            },
        ],
    },
    "notification": {
        "materials": [
            {
                "type": MaterialType.API_DOCUMENTATION,
                "name": "Notification API Documentation",
                "description": "Email/SMS/Push notification API documentation",
                "required": True,
            },
            {
                "type": MaterialType.CREDENTIAL_REFERENCE,
                "name": "Notification Credentials",
                "description": "Environment variable names for notification service API keys",
                "required": True,
            },
        ],
        "decisions": [
            {
                "type": DecisionType.ERROR_HANDLING,
                "question": "How should notification failures be handled?",
                "options": [
                    {"id": "retry", "label": "Retry sending", "description": "Retry failed notifications"},
                    {"id": "skip", "label": "Skip silently", "description": "Log and continue without retry"},
                    {"id": "queue", "label": "Queue for retry", "description": "Queue for later retry"},
                ],
                "default": "retry",
            },
        ],
    },
    "external_api": {
        "materials": [
            {
                "type": MaterialType.API_DOCUMENTATION,
                "name": "External API Documentation",
                "description": "API documentation (OpenAPI, Swagger, or manual)",
                "required": True,
            },
            {
                "type": MaterialType.CREDENTIAL_REFERENCE,
                "name": "API Credentials",
                "description": "Environment variable name for authentication",
                "required": True,
            },
        ],
        "decisions": [
            {
                "type": DecisionType.ERROR_HANDLING,
                "question": "How should API errors be handled?",
                "options": [
                    {"id": "retry", "label": "Retry with backoff", "description": "Automatic retry"},
                    {"id": "fail_fast", "label": "Fail immediately", "description": "Stop on error"},
                ],
                "default": "retry",
            },
        ],
    },
}

# Operation-specific additional requirements
OPERATION_REQUIREMENTS = {
    "sync": {
        "decisions": [
            {
                "type": DecisionType.SYNC_STRATEGY,
                "question": "What synchronization strategy should be used?",
                "options": [
                    {"id": "realtime", "label": "Real-time sync", "description": "Sync changes immediately as they occur"},
                    {"id": "batch", "label": "Batch sync", "description": "Sync in scheduled batches"},
                    {"id": "on_demand", "label": "On-demand", "description": "Sync only when requested"},
                ],
                "default": "batch",
            },
        ],
    },
    "transform": {
        "decisions": [
            {
                "type": DecisionType.DATA_TRANSFORM,
                "question": "How should data be transformed between systems?",
                "options": [
                    {"id": "auto", "label": "Auto-map fields", "description": "Automatically map matching field names"},
                    {"id": "manual", "label": "Manual mapping", "description": "Specify field mappings explicitly"},
                    {"id": "template", "label": "Use template", "description": "Use a transformation template"},
                ],
                "default": "auto",
            },
        ],
    },
}


class RequirementsEngine:
    """
    Infers integration requirements from parsed intent.

    Determines:
    - Required materials (API docs, credentials, examples)
    - Decisions needed from user (sync strategy, error handling)
    - Optional materials for better inference
    """

    def __init__(self) -> None:
        """Initialize the RequirementsEngine."""
        pass

    def infer(self, intent: "Intent") -> Requirements:
        """
        Infer requirements from a parsed intent.

        Args:
            intent: Parsed user intent

        Returns:
            Requirements object with materials and decisions needed
        """
        intent_id = self._generate_intent_id(intent)

        materials = self._infer_materials(intent)
        decisions = self._infer_decisions(intent)

        return Requirements(
            intent_id=intent_id,
            inferred_at=datetime.now(),
            materials=materials,
            decisions=decisions,
        )

    def _infer_materials(self, intent: "Intent") -> List[MaterialRequirement]:
        """Infer material requirements from intent."""
        materials = []

        # Get base requirements for integration type
        base_config = INTEGRATION_TYPE_REQUIREMENTS.get(
            intent.integration_type,
            INTEGRATION_TYPE_REQUIREMENTS.get("external_api", {}),
        )

        for i, mat_config in enumerate(base_config.get("materials", [])):
            material = MaterialRequirement(
                id=f"mat-{intent.integration_type}-{i:03d}",
                material_type=mat_config["type"],
                name=mat_config["name"],
                description=mat_config["description"],
                required=mat_config.get("required", True),
            )
            materials.append(material)

        return materials

    def _infer_decisions(self, intent: "Intent") -> List[DecisionRequirement]:
        """Infer decision requirements from intent."""
        decisions = []
        decision_ids_added = set()

        # Get base decisions for integration type
        base_config = INTEGRATION_TYPE_REQUIREMENTS.get(
            intent.integration_type,
            INTEGRATION_TYPE_REQUIREMENTS.get("external_api", {}),
        )

        for i, dec_config in enumerate(base_config.get("decisions", [])):
            decision_id = f"dec-{intent.integration_type}-{dec_config['type'].value}"
            if decision_id in decision_ids_added:
                continue

            decision = DecisionRequirement(
                id=decision_id,
                decision_type=dec_config["type"],
                question=dec_config["question"],
                options=[
                    DecisionOption(
                        id=opt["id"],
                        label=opt["label"],
                        description=opt["description"],
                    )
                    for opt in dec_config["options"]
                ],
                default=dec_config.get("default"),
            )
            decisions.append(decision)
            decision_ids_added.add(decision_id)

        # Add operation-specific decisions
        for operation in intent.operations:
            op_key = self._classify_operation(operation)
            if op_key and op_key in OPERATION_REQUIREMENTS:
                for dec_config in OPERATION_REQUIREMENTS[op_key].get("decisions", []):
                    decision_id = f"dec-op-{op_key}-{dec_config['type'].value}"
                    if decision_id in decision_ids_added:
                        continue

                    decision = DecisionRequirement(
                        id=decision_id,
                        decision_type=dec_config["type"],
                        question=dec_config["question"],
                        options=[
                            DecisionOption(
                                id=opt["id"],
                                label=opt["label"],
                                description=opt["description"],
                            )
                            for opt in dec_config["options"]
                        ],
                        default=dec_config.get("default"),
                    )
                    decisions.append(decision)
                    decision_ids_added.add(decision_id)

        return decisions

    def _classify_operation(self, operation: str) -> Optional[str]:
        """Classify an operation into a category for additional requirements."""
        operation_lower = operation.lower()

        if any(kw in operation_lower for kw in ["sync", "synchronize", "import", "export"]):
            return "sync"
        if any(kw in operation_lower for kw in ["transform", "convert", "map"]):
            return "transform"

        return None

    def _generate_intent_id(self, intent: "Intent") -> str:
        """Generate a unique ID for the intent-requirements link."""
        # Use a combination of type, service, and UUID
        service = intent.target_service or "unknown"
        short_uuid = str(uuid.uuid4())[:8]
        return f"{intent.integration_type}-{service}-{short_uuid}".lower()
