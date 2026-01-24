"""
ProcessOS Agent Types Module

Data models for dynamic agent and squad management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(Enum):
    """Status of an agent."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"  # Replaced by a better agent


class SquadStatus(Enum):
    """Status of a squad."""

    ASSEMBLING = "assembling"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class CoordinationType(Enum):
    """Types of agent coordination."""

    HANDOFF = "handoff"  # Pass context to next agent
    BROADCAST = "broadcast"  # Share result with all agents
    WAIT = "wait"  # Wait for agent to complete
    PARALLEL = "parallel"  # Run agents in parallel


@dataclass
class AgentCapability:
    """A capability that an agent possesses."""

    name: str  # e.g., "api_parsing", "code_generation"
    description: str  # What this capability does
    semantic_tags: List[str] = field(default_factory=list)  # Tags for matching
    confidence: float = 1.0  # How well the agent performs this (0-1)


@dataclass
class Agent:
    """A dynamically created agent with specific capabilities."""

    id: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)

    # Capabilities
    capabilities: List[AgentCapability] = field(default_factory=list)

    # Contracts
    input_contract: Dict[str, Any] = field(default_factory=dict)  # Expected input schema
    output_contract: Dict[str, Any] = field(default_factory=dict)  # Expected output schema

    # Context
    system_prompt: str = ""  # Agent's system prompt template
    context_requirements: List[str] = field(default_factory=list)  # What context this agent needs

    # Reuse tracking
    times_used: int = 0
    last_used_at: Optional[datetime] = None

    # Status
    status: AgentStatus = AgentStatus.ACTIVE

    def use(self) -> None:
        """Record agent usage."""
        self.times_used += 1
        self.last_used_at = datetime.now()

    def deprecate(self) -> None:
        """Mark agent as deprecated."""
        self.status = AgentStatus.DEPRECATED

    def supersede(self) -> None:
        """Mark agent as superseded by a better version."""
        self.status = AgentStatus.SUPERSEDED

    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return any(c.name == capability_name for c in self.capabilities)

    def get_capability_tags(self) -> List[str]:
        """Get all semantic tags from all capabilities."""
        tags = []
        for cap in self.capabilities:
            tags.extend(cap.semantic_tags)
        return list(set(tags))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "semantic_tags": c.semantic_tags,
                    "confidence": c.confidence,
                }
                for c in self.capabilities
            ],
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "system_prompt": self.system_prompt,
            "context_requirements": self.context_requirements,
            "times_used": self.times_used,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        """Deserialize from dictionary."""
        capabilities = [
            AgentCapability(
                name=c["name"],
                description=c["description"],
                semantic_tags=c.get("semantic_tags", []),
                confidence=c.get("confidence", 1.0),
            )
            for c in data.get("capabilities", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            capabilities=capabilities,
            input_contract=data.get("input_contract", {}),
            output_contract=data.get("output_contract", {}),
            system_prompt=data.get("system_prompt", ""),
            context_requirements=data.get("context_requirements", []),
            times_used=data.get("times_used", 0),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            status=AgentStatus(data.get("status", "active")),
        )


@dataclass
class SquadMember:
    """An agent assigned to a squad with a specific role."""

    agent_id: str
    role: str  # Role in this squad (e.g., "mapper", "generator")
    assigned_steps: List[str] = field(default_factory=list)  # Step IDs this agent handles
    priority: int = 1  # Execution priority (lower = earlier)


@dataclass
class CoordinationRule:
    """A rule for coordinating agents in a squad."""

    rule_type: CoordinationType
    source_agent: str  # Agent ID or "any"
    target_agent: str  # Agent ID or "all"
    trigger: str  # What triggers this rule
    action: str  # What action to take


@dataclass
class Squad:
    """A composed group of agents for executing an integration workflow."""

    id: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)

    # Composition
    agents: List[SquadMember] = field(default_factory=list)

    # Coordination
    coordination_rules: List[CoordinationRule] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)

    # Execution
    playbook_id: Optional[str] = None
    status: SquadStatus = SquadStatus.ASSEMBLING

    # Results
    completed_steps: List[str] = field(default_factory=list)
    current_step: Optional[str] = None

    def add_member(self, member: SquadMember) -> None:
        """Add a member to the squad."""
        self.agents.append(member)

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the squad."""
        for i, member in enumerate(self.agents):
            if member.agent_id == agent_id:
                self.agents.pop(i)
                return True
        return False

    def get_member(self, agent_id: str) -> Optional[SquadMember]:
        """Get a squad member by agent ID."""
        for member in self.agents:
            if member.agent_id == agent_id:
                return member
        return None

    def get_agents_for_step(self, step_id: str) -> List[SquadMember]:
        """Get agents assigned to a specific step."""
        return [m for m in self.agents if step_id in m.assigned_steps]

    def ready(self) -> None:
        """Mark squad as ready to execute."""
        if not self.agents:
            raise ValueError("Cannot mark empty squad as ready")
        self.status = SquadStatus.READY

    def start(self) -> None:
        """Start squad execution."""
        self.status = SquadStatus.EXECUTING

    def complete_step(self, step_id: str) -> None:
        """Mark a step as completed."""
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

    def complete(self) -> None:
        """Mark squad as completed."""
        self.status = SquadStatus.COMPLETED

    def fail(self) -> None:
        """Mark squad as failed."""
        self.status = SquadStatus.FAILED

    def update_context(self, key: str, value: Any) -> None:
        """Update shared context."""
        self.shared_context[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "agents": [
                {
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "assigned_steps": m.assigned_steps,
                    "priority": m.priority,
                }
                for m in self.agents
            ],
            "coordination_rules": [
                {
                    "rule_type": r.rule_type.value,
                    "source_agent": r.source_agent,
                    "target_agent": r.target_agent,
                    "trigger": r.trigger,
                    "action": r.action,
                }
                for r in self.coordination_rules
            ],
            "shared_context": self.shared_context,
            "playbook_id": self.playbook_id,
            "status": self.status.value,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Squad":
        """Deserialize from dictionary."""
        agents = [
            SquadMember(
                agent_id=m["agent_id"],
                role=m["role"],
                assigned_steps=m.get("assigned_steps", []),
                priority=m.get("priority", 1),
            )
            for m in data.get("agents", [])
        ]

        coordination_rules = [
            CoordinationRule(
                rule_type=CoordinationType(r["rule_type"]),
                source_agent=r["source_agent"],
                target_agent=r["target_agent"],
                trigger=r["trigger"],
                action=r["action"],
            )
            for r in data.get("coordination_rules", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            agents=agents,
            coordination_rules=coordination_rules,
            shared_context=data.get("shared_context", {}),
            playbook_id=data.get("playbook_id"),
            status=SquadStatus(data.get("status", "assembling")),
            completed_steps=data.get("completed_steps", []),
            current_step=data.get("current_step"),
        )
