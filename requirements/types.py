"""
ProcessOS Requirements Types Module

Data models for integration requirements and material collection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MaterialType(Enum):
    """Types of materials that can be collected."""

    API_DOCUMENTATION = "api_documentation"
    CREDENTIAL_REFERENCE = "credential_reference"  # Env var name only
    EXAMPLE_REQUEST = "example_request"
    EXAMPLE_RESPONSE = "example_response"
    CONFIGURATION = "configuration"
    SCHEMA_FILE = "schema_file"


class DecisionType(Enum):
    """Types of decisions that require user input."""

    SYNC_STRATEGY = "sync_strategy"  # Real-time vs batch
    ERROR_HANDLING = "error_handling"  # Retry, fail, alert
    DATA_TRANSFORM = "data_transform"  # How to transform data
    AUTHENTICATION = "authentication"  # Auth method to use
    SCOPE_REFINEMENT = "scope_refinement"  # Narrow down operations


@dataclass
class DecisionOption:
    """An option for a decision."""

    id: str
    label: str
    description: str


@dataclass
class MaterialRequirement:
    """A material (document, credential, etc.) needed for integration."""

    id: str
    material_type: MaterialType
    name: str
    description: str  # Why this is needed
    required: bool = True

    # Status
    satisfied: bool = False
    satisfied_by: Optional[str] = None  # Reference to collected material


@dataclass
class DecisionRequirement:
    """A decision that requires user input."""

    id: str
    decision_type: DecisionType
    question: str
    options: List[DecisionOption]
    default: Optional[str] = None

    # Status
    decided: bool = False
    decision: Optional[str] = None


@dataclass
class Requirements:
    """Requirements inferred for an integration."""

    intent_id: str
    inferred_at: datetime = field(default_factory=datetime.now)

    # Materials needed
    materials: List[MaterialRequirement] = field(default_factory=list)

    # Decisions needed
    decisions: List[DecisionRequirement] = field(default_factory=list)

    @property
    def all_satisfied(self) -> bool:
        """Check if all required materials are satisfied and decisions made."""
        required_materials_satisfied = all(m.satisfied for m in self.materials if m.required)
        all_decisions_made = all(d.decided for d in self.decisions)
        return required_materials_satisfied and all_decisions_made

    @property
    def pending_materials(self) -> List[MaterialRequirement]:
        """Get list of unsatisfied required materials."""
        return [m for m in self.materials if m.required and not m.satisfied]

    @property
    def pending_decisions(self) -> List[DecisionRequirement]:
        """Get list of undecided decisions."""
        return [d for d in self.decisions if not d.decided]

    def satisfy_material(self, material_id: str, satisfied_by: str) -> bool:
        """Mark a material requirement as satisfied."""
        for material in self.materials:
            if material.id == material_id:
                material.satisfied = True
                material.satisfied_by = satisfied_by
                return True
        return False

    def make_decision(self, decision_id: str, option_id: str) -> bool:
        """Record a decision."""
        for decision in self.decisions:
            if decision.id == decision_id:
                decision.decided = True
                decision.decision = option_id
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "intent_id": self.intent_id,
            "inferred_at": self.inferred_at.isoformat(),
            "materials": [
                {
                    "id": m.id,
                    "material_type": m.material_type.value,
                    "name": m.name,
                    "description": m.description,
                    "required": m.required,
                    "satisfied": m.satisfied,
                    "satisfied_by": m.satisfied_by,
                }
                for m in self.materials
            ],
            "decisions": [
                {
                    "id": d.id,
                    "decision_type": d.decision_type.value,
                    "question": d.question,
                    "options": [
                        {"id": o.id, "label": o.label, "description": o.description}
                        for o in d.options
                    ],
                    "default": d.default,
                    "decided": d.decided,
                    "decision": d.decision,
                }
                for d in self.decisions
            ],
            "all_satisfied": self.all_satisfied,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Requirements":
        """Deserialize from dictionary."""
        materials = [
            MaterialRequirement(
                id=m["id"],
                material_type=MaterialType(m["material_type"]),
                name=m["name"],
                description=m["description"],
                required=m.get("required", True),
                satisfied=m.get("satisfied", False),
                satisfied_by=m.get("satisfied_by"),
            )
            for m in data.get("materials", [])
        ]

        decisions = [
            DecisionRequirement(
                id=d["id"],
                decision_type=DecisionType(d["decision_type"]),
                question=d["question"],
                options=[
                    DecisionOption(
                        id=o["id"],
                        label=o["label"],
                        description=o["description"],
                    )
                    for o in d.get("options", [])
                ],
                default=d.get("default"),
                decided=d.get("decided", False),
                decision=d.get("decision"),
            )
            for d in data.get("decisions", [])
        ]

        return cls(
            intent_id=data["intent_id"],
            inferred_at=datetime.fromisoformat(data["inferred_at"]) if "inferred_at" in data else datetime.now(),
            materials=materials,
            decisions=decisions,
        )
