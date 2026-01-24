"""
ProcessOS Playbook Types Module

Data models for dynamic playbook generation and execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PlaybookStatus(Enum):
    """Status of a playbook."""

    DRAFT = "draft"  # Generated, not approved
    APPROVED = "approved"  # User approved, not started
    IN_PROGRESS = "in_progress"  # Executing
    BLOCKED = "blocked"  # Waiting on gate/input
    COMPLETED = "completed"
    FAILED = "failed"


class StepType(Enum):
    """Types of playbook steps."""

    DISCOVERY = "discovery"
    INTENT_ANALYSIS = "intent_analysis"
    REQUIREMENTS_GATHER = "requirements_gather"
    MATERIAL_COLLECTION = "material_collection"
    SCHEMA_MAPPING = "schema_mapping"
    USER_CONFIRMATION = "user_confirmation"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CODE_APPLICATION = "code_application"


class StepStatus(Enum):
    """Status of a playbook step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


class GateType(Enum):
    """Types of validation gates."""

    SCHEMA_VALIDATION = "schema_validation"
    USER_APPROVAL = "user_approval"
    COMPLETENESS_CHECK = "completeness_check"
    CONFLICT_DETECTION = "conflict_detection"


class GateStatus(Enum):
    """Status of a gate."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BYPASSED = "bypassed"  # User override


@dataclass
class PlaybookStep:
    """A step in the playbook."""

    id: str
    name: str
    description: str
    step_type: StepType

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on

    # Execution
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def start(self) -> None:
        """Mark step as started."""
        self.status = StepStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self) -> None:
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now()

    def fail(self, error: str) -> None:
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def block(self, reason: str) -> None:
        """Mark step as blocked."""
        self.status = StepStatus.BLOCKED
        self.error = reason

    def skip(self) -> None:
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = datetime.now()


@dataclass
class PlaybookGate:
    """A validation checkpoint in the playbook."""

    id: str
    name: str
    gate_type: GateType
    after_step: str  # Step ID after which this gate runs

    # Gate configuration
    validation_rules: List[str] = field(default_factory=list)

    # Status
    status: GateStatus = GateStatus.PENDING
    checked_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    def pass_gate(self) -> None:
        """Mark gate as passed."""
        self.status = GateStatus.PASSED
        self.checked_at = datetime.now()

    def fail_gate(self, reason: str) -> None:
        """Mark gate as failed."""
        self.status = GateStatus.FAILED
        self.failure_reason = reason
        self.checked_at = datetime.now()

    def bypass(self) -> None:
        """Mark gate as bypassed (user override)."""
        self.status = GateStatus.BYPASSED
        self.checked_at = datetime.now()


@dataclass
class DynamicPlaybook:
    """A dynamically generated playbook for an integration."""

    id: str
    intent_id: str
    created_at: datetime = field(default_factory=datetime.now)

    # Playbook content
    name: str = ""
    description: str = ""

    # Steps
    steps: List[PlaybookStep] = field(default_factory=list)

    # Gates
    gates: List[PlaybookGate] = field(default_factory=list)

    # User approval
    user_approved: bool = False
    approved_at: Optional[datetime] = None

    # Execution status
    current_step: Optional[str] = None
    status: PlaybookStatus = PlaybookStatus.DRAFT

    def approve(self) -> None:
        """Mark playbook as approved by user."""
        self.user_approved = True
        self.approved_at = datetime.now()
        self.status = PlaybookStatus.APPROVED

    def start_execution(self) -> None:
        """Start playbook execution."""
        if not self.user_approved:
            raise ValueError("Cannot start execution without user approval")
        self.status = PlaybookStatus.IN_PROGRESS
        if self.steps:
            self.current_step = self.steps[0].id

    def get_step(self, step_id: str) -> Optional[PlaybookStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_gate_after_step(self, step_id: str) -> Optional[PlaybookGate]:
        """Get the gate that runs after a step."""
        for gate in self.gates:
            if gate.after_step == step_id:
                return gate
        return None

    def get_next_step(self, current_step_id: str) -> Optional[PlaybookStep]:
        """Get the next step after the current one."""
        found_current = False
        for step in self.steps:
            if found_current:
                return step
            if step.id == current_step_id:
                found_current = True
        return None

    def get_ready_steps(self) -> List[PlaybookStep]:
        """Get steps that are ready to execute (all dependencies completed)."""
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        ready = []
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                if all(dep in completed_ids for dep in step.depends_on):
                    ready.append(step)
        return ready

    def complete(self) -> None:
        """Mark playbook as completed."""
        self.status = PlaybookStatus.COMPLETED

    def fail(self) -> None:
        """Mark playbook as failed."""
        self.status = PlaybookStatus.FAILED

    def block(self) -> None:
        """Mark playbook as blocked."""
        self.status = PlaybookStatus.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for YAML storage."""
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "created_at": self.created_at.isoformat(),
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "step_type": s.step_type.value,
                    "depends_on": s.depends_on,
                    "status": s.status.value,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "gates": [
                {
                    "id": g.id,
                    "name": g.name,
                    "gate_type": g.gate_type.value,
                    "after_step": g.after_step,
                    "validation_rules": g.validation_rules,
                    "status": g.status.value,
                    "checked_at": g.checked_at.isoformat() if g.checked_at else None,
                    "failure_reason": g.failure_reason,
                }
                for g in self.gates
            ],
            "user_approved": self.user_approved,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "current_step": self.current_step,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DynamicPlaybook":
        """Deserialize from dictionary."""
        steps = [
            PlaybookStep(
                id=s["id"],
                name=s["name"],
                description=s["description"],
                step_type=StepType(s["step_type"]),
                depends_on=s.get("depends_on", []),
                status=StepStatus(s.get("status", "pending")),
                started_at=datetime.fromisoformat(s["started_at"]) if s.get("started_at") else None,
                completed_at=datetime.fromisoformat(s["completed_at"]) if s.get("completed_at") else None,
                error=s.get("error"),
            )
            for s in data.get("steps", [])
        ]

        gates = [
            PlaybookGate(
                id=g["id"],
                name=g["name"],
                gate_type=GateType(g["gate_type"]),
                after_step=g["after_step"],
                validation_rules=g.get("validation_rules", []),
                status=GateStatus(g.get("status", "pending")),
                checked_at=datetime.fromisoformat(g["checked_at"]) if g.get("checked_at") else None,
                failure_reason=g.get("failure_reason"),
            )
            for g in data.get("gates", [])
        ]

        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=steps,
            gates=gates,
            user_approved=data.get("user_approved", False),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
            current_step=data.get("current_step"),
            status=PlaybookStatus(data.get("status", "draft")),
        )
