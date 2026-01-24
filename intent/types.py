"""
ProcessOS Intent Types Module

Data models for parsed user integration intents.
Handles intent classification, scope determination, and clarification flow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class IntegrationScope(Enum):
    """Scope of the integration operations."""

    FULL_CRUD = "full_crud"
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"
    SPECIFIC_OPERATIONS = "specific_operations"


@dataclass
class ClarificationOption:
    """An option for a clarification question."""

    id: str
    label: str
    description: str
    implications: str  # What this choice means


@dataclass
class Clarification:
    """A question that needs user input."""

    id: str
    question: str
    options: List[ClarificationOption]
    default: Optional[str] = None  # Recommended default option id
    priority: int = 2  # 1=critical, 2=important, 3=nice-to-have


@dataclass
class ResolvedClarification:
    """A clarification that has been answered."""

    clarification_id: str
    selected_option: str  # Option id or 'custom'
    custom_value: Optional[str] = None  # If custom was selected
    resolved_at: datetime = field(default_factory=datetime.now)


@dataclass
class Intent:
    """Parsed user integration intent."""

    # Core intent
    raw_request: str
    integration_type: str  # Classified type (supplier_api, payment, etc.)
    target_service: Optional[str] = None  # Specific service name (DHL, Stripe, etc.)

    # Scope
    scope: IntegrationScope = IntegrationScope.FULL_CRUD
    operations: List[str] = field(default_factory=list)  # Specific operations if scope is specific

    # Analysis metadata
    analyzed_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0  # 0-1

    # Clarification
    clarifications_needed: List[Clarification] = field(default_factory=list)
    clarifications_resolved: List[ResolvedClarification] = field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        """Check if any clarifications are still needed."""
        resolved_ids = {c.clarification_id for c in self.clarifications_resolved}
        return any(c.id not in resolved_ids for c in self.clarifications_needed)

    @property
    def pending_clarifications(self) -> List[Clarification]:
        """Get list of unresolved clarifications."""
        resolved_ids = {c.clarification_id for c in self.clarifications_resolved}
        return [c for c in self.clarifications_needed if c.id not in resolved_ids]

    def resolve_clarification(self, clarification_id: str, option_id: str, custom_value: Optional[str] = None) -> None:
        """Resolve a pending clarification."""
        self.clarifications_resolved.append(
            ResolvedClarification(
                clarification_id=clarification_id,
                selected_option=option_id,
                custom_value=custom_value,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "raw_request": self.raw_request,
            "integration_type": self.integration_type,
            "target_service": self.target_service,
            "scope": self.scope.value,
            "operations": self.operations,
            "analyzed_at": self.analyzed_at.isoformat(),
            "confidence": self.confidence,
            "clarifications_needed": [
                {
                    "id": c.id,
                    "question": c.question,
                    "options": [
                        {
                            "id": o.id,
                            "label": o.label,
                            "description": o.description,
                            "implications": o.implications,
                        }
                        for o in c.options
                    ],
                    "default": c.default,
                    "priority": c.priority,
                }
                for c in self.clarifications_needed
            ],
            "clarifications_resolved": [
                {
                    "clarification_id": r.clarification_id,
                    "selected_option": r.selected_option,
                    "custom_value": r.custom_value,
                    "resolved_at": r.resolved_at.isoformat(),
                }
                for r in self.clarifications_resolved
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intent":
        """Deserialize from dictionary."""
        clarifications_needed = [
            Clarification(
                id=c["id"],
                question=c["question"],
                options=[
                    ClarificationOption(
                        id=o["id"],
                        label=o["label"],
                        description=o["description"],
                        implications=o["implications"],
                    )
                    for o in c.get("options", [])
                ],
                default=c.get("default"),
                priority=c.get("priority", 2),
            )
            for c in data.get("clarifications_needed", [])
        ]

        clarifications_resolved = [
            ResolvedClarification(
                clarification_id=r["clarification_id"],
                selected_option=r["selected_option"],
                custom_value=r.get("custom_value"),
                resolved_at=datetime.fromisoformat(r["resolved_at"]) if "resolved_at" in r else datetime.now(),
            )
            for r in data.get("clarifications_resolved", [])
        ]

        return cls(
            raw_request=data["raw_request"],
            integration_type=data["integration_type"],
            target_service=data.get("target_service"),
            scope=IntegrationScope(data.get("scope", "full_crud")),
            operations=data.get("operations", []),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]) if "analyzed_at" in data else datetime.now(),
            confidence=data.get("confidence", 0.0),
            clarifications_needed=clarifications_needed,
            clarifications_resolved=clarifications_resolved,
        )
