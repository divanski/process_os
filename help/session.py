"""
ProcessOS Interactive Session

Tracks state during interactive mode workflows.
Manages wizard progression, user inputs, and session history.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class SessionState(Enum):
    """Current state of an interactive session."""
    WELCOME = "welcome"
    SELECT_WORKFLOW = "select_workflow"
    COLLECT_INPUTS = "collect_inputs"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class SessionHistoryEntry:
    """A single entry in the session history."""
    timestamp: datetime
    command: str
    result: str  # "success" | "error" | "skipped"
    details: Optional[str] = None


@dataclass
class InteractiveSession:
    """
    Tracks state during interactive mode workflows.

    Attributes:
        session_id: Unique session identifier
        started_at: When the session started
        last_activity: Last user interaction time
        current_state: Current wizard state
        completed_steps: List of completed step IDs
        inputs: Collected user inputs
        context: Session context (project info, detected stack, etc.)
        workflow_type: Type of workflow being executed
        workflow_target: Target of the workflow (e.g., "DHL" for courier integration)
        history: Command history for this session
    """
    session_id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:12]}")
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # State tracking
    current_state: SessionState = SessionState.WELCOME
    completed_steps: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)

    # Context
    context: Dict[str, Any] = field(default_factory=dict)

    # Workflow
    workflow_type: Optional[str] = None
    workflow_target: Optional[str] = None

    # History
    history: List[SessionHistoryEntry] = field(default_factory=list)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def transition_to(self, new_state: SessionState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to
        """
        self.completed_steps.append(self.current_state.value)
        self.current_state = new_state
        self.update_activity()

    def add_input(self, key: str, value: Any) -> None:
        """
        Add a user input to the session.

        Args:
            key: Input identifier
            value: Input value
        """
        self.inputs[key] = value
        self.update_activity()

    def add_history(self, command: str, result: str, details: Optional[str] = None) -> None:
        """
        Add an entry to the session history.

        Args:
            command: The command that was executed
            result: Result of the command ("success", "error", "skipped")
            details: Optional details about the result
        """
        self.history.append(SessionHistoryEntry(
            timestamp=datetime.now(),
            command=command,
            result=result,
            details=details
        ))
        self.update_activity()

    def set_workflow(self, workflow_type: str, target: Optional[str] = None) -> None:
        """
        Set the current workflow.

        Args:
            workflow_type: Type of workflow (e.g., "courier_integration", "custom", "learn")
            target: Optional target (e.g., "DHL", "Speedy")
        """
        self.workflow_type = workflow_type
        self.workflow_target = target
        self.update_activity()

    def set_context(self, **kwargs) -> None:
        """
        Update session context.

        Args:
            **kwargs: Context key-value pairs to set
        """
        self.context.update(kwargs)
        self.update_activity()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to a dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "state": {
                "current_step": self.current_state.value,
                "completed_steps": self.completed_steps,
                "inputs": self.inputs,
            },
            "context": self.context,
            "workflow": {
                "type": self.workflow_type,
                "target": self.workflow_target,
            },
            "history": [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "command": h.command,
                    "result": h.result,
                    "details": h.details,
                }
                for h in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractiveSession":
        """Create a session from a dictionary."""
        session = cls(
            session_id=data["session_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            current_state=SessionState(data["state"]["current_step"]),
            completed_steps=data["state"]["completed_steps"],
            inputs=data["state"]["inputs"],
            context=data.get("context", {}),
            workflow_type=data.get("workflow", {}).get("type"),
            workflow_target=data.get("workflow", {}).get("target"),
        )

        for h in data.get("history", []):
            session.history.append(SessionHistoryEntry(
                timestamp=datetime.fromisoformat(h["timestamp"]),
                command=h["command"],
                result=h["result"],
                details=h.get("details"),
            ))

        return session
