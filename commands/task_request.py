"""
ProcessOS Task Request

Structured representation of a user command.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TaskTarget:
    """Target of a task request."""

    name: str
    identifier: str
    type: str  # courier, api, service, component, module, custom

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "identifier": self.identifier,
            "name": self.name,
            "type": self.type,
        }


@dataclass
class TaskParameters:
    """Parameters for a task request."""

    priority: str = "medium"
    capabilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with sorted keys."""
        return {
            "capabilities": sorted(self.capabilities),
            "constraints": sorted(self.constraints),
            "options": dict(sorted(self.options.items())),
            "priority": self.priority,
        }


@dataclass
class TaskContext:
    """Context information for a task request."""

    original_command: str = ""
    parsed_at: str = ""
    host_root: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        d = {}
        if self.original_command:
            d["original_command"] = self.original_command
        if self.parsed_at:
            d["parsed_at"] = self.parsed_at
        if self.host_root:
            d["host_root"] = self.host_root
        return dict(sorted(d.items()))


@dataclass
class TaskRequest:
    """
    Structured representation of a user command.

    Determinism guarantees:
    - Same command text = same command_id
    - Same command text = same to_dict() output
    - No random or time-dependent values in core fields
    """

    command_id: str
    intent: str
    target: TaskTarget
    parameters: TaskParameters
    context: TaskContext = field(default_factory=TaskContext)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with sorted keys for determinism.

        Output matches task-request.schema.json.
        """
        return {
            "command_id": self.command_id,
            "context": self.context.to_dict(),
            "intent": self.intent,
            "parameters": self.parameters.to_dict(),
            "target": self.target.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to deterministic JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRequest":
        """Create TaskRequest from dictionary."""
        target_data = data.get("target", {})
        target = TaskTarget(
            name=target_data.get("name", ""),
            identifier=target_data.get("identifier", ""),
            type=target_data.get("type", "custom"),
        )

        params_data = data.get("parameters", {})
        parameters = TaskParameters(
            priority=params_data.get("priority", "medium"),
            capabilities=params_data.get("capabilities", []),
            constraints=params_data.get("constraints", []),
            options=params_data.get("options", {}),
        )

        context_data = data.get("context", {})
        context = TaskContext(
            original_command=context_data.get("original_command", ""),
            parsed_at=context_data.get("parsed_at", ""),
            host_root=context_data.get("host_root", ""),
        )

        return cls(
            command_id=data.get("command_id", ""),
            intent=data.get("intent", "custom"),
            target=target,
            parameters=parameters,
            context=context,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "TaskRequest":
        """Create TaskRequest from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_workspace_id(self) -> str:
        """
        Generate workspace ID from command ID.

        Workspace ID is derived from command_id to ensure
        same command always maps to same workspace.
        """
        # Extract hash from command_id and prefix with ws-
        if self.command_id.startswith("cmd-"):
            return f"ws-{self.command_id[4:]}"
        # Fallback: hash the command_id
        hash_hex = hashlib.sha256(self.command_id.encode()).hexdigest()[:12]
        return f"ws-{hash_hex}"
