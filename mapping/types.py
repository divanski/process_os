"""
ProcessOS Mapping Types Module

Data models for schema mapping between external APIs and local models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Transformation:
    """A transformation to apply during mapping."""

    type: str  # 'type_cast', 'format', 'compute', 'rename'
    expression: str  # Transformation expression/function
    description: str  # Human-readable explanation


@dataclass
class FieldMapping:
    """A mapping between an external field and local field."""

    id: str

    # External side
    external_endpoint: str  # Which endpoint
    external_field_path: str  # JSON path (e.g., "data.product.name")
    external_type: str  # API field type

    # Local side
    local_model: str  # Model name
    local_field: str  # Field name
    local_type: str  # Local field type

    # Transformation
    transformation: Optional[Transformation] = None

    # Confidence and reasoning
    confidence: float = 0.0  # 0-1
    reasoning: str = ""  # Why this mapping was suggested

    # User feedback
    user_approved: Optional[bool] = None  # None = pending, True/False = decided
    user_override: Optional[str] = None  # If user selected different mapping


@dataclass
class UnmappedField:
    """A field that couldn't be automatically mapped."""

    source: str  # 'external' or 'local'
    field_path: str  # Field identifier
    field_type: str  # Field type
    reason: str  # Why not mapped


@dataclass
class SchemaMapping:
    """Complete mapping between external API and local models."""

    intent_id: str
    materials_id: str
    created_at: datetime = field(default_factory=datetime.now)

    # Individual field mappings
    field_mappings: List[FieldMapping] = field(default_factory=list)

    # Unmapped fields
    unmapped_external: List[UnmappedField] = field(default_factory=list)
    unmapped_local: List[UnmappedField] = field(default_factory=list)

    # User confirmation status
    user_confirmed: bool = False
    confirmed_at: Optional[datetime] = None

    @property
    def pending_approvals(self) -> List[FieldMapping]:
        """Get mappings awaiting user approval."""
        return [m for m in self.field_mappings if m.user_approved is None]

    @property
    def approved_mappings(self) -> List[FieldMapping]:
        """Get user-approved mappings."""
        return [m for m in self.field_mappings if m.user_approved is True]

    @property
    def rejected_mappings(self) -> List[FieldMapping]:
        """Get user-rejected mappings."""
        return [m for m in self.field_mappings if m.user_approved is False]

    @property
    def all_decided(self) -> bool:
        """Check if all mappings have user decisions."""
        return all(m.user_approved is not None for m in self.field_mappings)

    def approve_mapping(self, mapping_id: str) -> bool:
        """Approve a mapping."""
        for mapping in self.field_mappings:
            if mapping.id == mapping_id:
                mapping.user_approved = True
                return True
        return False

    def reject_mapping(self, mapping_id: str) -> bool:
        """Reject a mapping."""
        for mapping in self.field_mappings:
            if mapping.id == mapping_id:
                mapping.user_approved = False
                return True
        return False

    def override_mapping(self, mapping_id: str, new_local_field: str) -> bool:
        """Override a mapping with a different local field."""
        for mapping in self.field_mappings:
            if mapping.id == mapping_id:
                mapping.user_override = new_local_field
                mapping.user_approved = True
                return True
        return False

    def confirm_all(self) -> None:
        """Mark all mappings as confirmed by user."""
        self.user_confirmed = True
        self.confirmed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "intent_id": self.intent_id,
            "materials_id": self.materials_id,
            "created_at": self.created_at.isoformat(),
            "field_mappings": [
                {
                    "id": m.id,
                    "external_endpoint": m.external_endpoint,
                    "external_field_path": m.external_field_path,
                    "external_type": m.external_type,
                    "local_model": m.local_model,
                    "local_field": m.local_field,
                    "local_type": m.local_type,
                    "transformation": {
                        "type": m.transformation.type,
                        "expression": m.transformation.expression,
                        "description": m.transformation.description,
                    } if m.transformation else None,
                    "confidence": m.confidence,
                    "reasoning": m.reasoning,
                    "user_approved": m.user_approved,
                    "user_override": m.user_override,
                }
                for m in self.field_mappings
            ],
            "unmapped_external": [
                {
                    "source": u.source,
                    "field_path": u.field_path,
                    "field_type": u.field_type,
                    "reason": u.reason,
                }
                for u in self.unmapped_external
            ],
            "unmapped_local": [
                {
                    "source": u.source,
                    "field_path": u.field_path,
                    "field_type": u.field_type,
                    "reason": u.reason,
                }
                for u in self.unmapped_local
            ],
            "user_confirmed": self.user_confirmed,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaMapping":
        """Deserialize from dictionary."""
        field_mappings = []
        for m in data.get("field_mappings", []):
            transformation = None
            if m.get("transformation"):
                transformation = Transformation(
                    type=m["transformation"]["type"],
                    expression=m["transformation"]["expression"],
                    description=m["transformation"]["description"],
                )
            field_mappings.append(
                FieldMapping(
                    id=m["id"],
                    external_endpoint=m["external_endpoint"],
                    external_field_path=m["external_field_path"],
                    external_type=m["external_type"],
                    local_model=m["local_model"],
                    local_field=m["local_field"],
                    local_type=m["local_type"],
                    transformation=transformation,
                    confidence=m.get("confidence", 0.0),
                    reasoning=m.get("reasoning", ""),
                    user_approved=m.get("user_approved"),
                    user_override=m.get("user_override"),
                )
            )

        unmapped_external = [
            UnmappedField(
                source=u["source"],
                field_path=u["field_path"],
                field_type=u["field_type"],
                reason=u["reason"],
            )
            for u in data.get("unmapped_external", [])
        ]

        unmapped_local = [
            UnmappedField(
                source=u["source"],
                field_path=u["field_path"],
                field_type=u["field_type"],
                reason=u["reason"],
            )
            for u in data.get("unmapped_local", [])
        ]

        return cls(
            intent_id=data["intent_id"],
            materials_id=data["materials_id"],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            field_mappings=field_mappings,
            unmapped_external=unmapped_external,
            unmapped_local=unmapped_local,
            user_confirmed=data.get("user_confirmed", False),
            confirmed_at=datetime.fromisoformat(data["confirmed_at"]) if data.get("confirmed_at") else None,
        )
