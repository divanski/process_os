"""
ProcessOS Telemetry

Emits lifecycle events to JSONL file sink.

Terminal events (exactly one per run):
- run_succeeded: All steps completed successfully
- run_failed: Unrecoverable error
- run_halted: System halt (drift, invariant violation)
- run_blocked: Awaiting user input (resumable)

Non-terminal events:
- run_started, run_resumed
- step_started, step_completed, step_failed
- gate_passed, gate_failed, gate_halted
- agent_message: User-visible message
- artifact_registered

DEPRECATED (Sprint 9.1, removal in Sprint 11):
- run_completed: Alias for run_succeeded. Use run_succeeded instead.
  Emitted automatically alongside run_succeeded for backward compatibility.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional


class RunStatus(str, Enum):
    """Run status enum - single source of truth."""

    RUNNING = "running"      # Non-terminal: run in progress
    SUCCEEDED = "succeeded"  # Terminal: all steps completed successfully
    FAILED = "failed"        # Terminal: unrecoverable error
    HALTED = "halted"        # Terminal: system halt (drift, invariant violation)
    BLOCKED = "blocked"      # Terminal-but-resumable: awaiting user input


# Terminal event types - exactly one per run
TERMINAL_EVENTS = {"run_succeeded", "run_failed", "run_halted", "run_blocked"}


class ObservabilityMode:
    """
    Observability mode settings (T056).

    Controls which events are emitted based on user preference.
    """

    MINIMAL = "minimal"   # Only terminal events and errors
    FULL = "full"         # All events
    SILENT = "silent"     # No telemetry (only critical halts)

    @classmethod
    def get_filtered_events(cls, mode: str) -> set:
        """Get event types to emit for a given mode."""
        if mode == cls.SILENT:
            # Only critical system halts
            return {"run_halted", "drift_detected"}

        if mode == cls.MINIMAL:
            # Terminal events, errors, and key progress markers
            return {
                "run_started",
                "run_succeeded",
                "run_failed",
                "run_halted",
                "run_blocked",
                "run_resumed",
                "step_failed",
                "gate_halted",
                "drift_detected",
                "agent_message",  # Keep user-visible messages
            }

        # FULL mode - all events
        return TelemetrySink.EVENT_TYPES.copy()


class TelemetrySink:
    """
    JSONL file sink for telemetry events.

    All events are append-only with deterministic structure.
    Supports observability modes (T056) for controlling event verbosity.
    """

    # Valid event types
    EVENT_TYPES = {
        # Terminal events (exactly one per run)
        "run_succeeded",    # Canonical terminal success (Sprint 9+)
        "run_completed",    # DEPRECATED: Alias for run_succeeded (removed in Sprint 11)
        "run_failed",
        "run_halted",
        "run_blocked",      # Awaiting user input (resumable)
        # Non-terminal events
        "run_started",
        "run_resumed",      # Blocked run continues
        "step_started",
        "step_completed",
        "step_halted",
        "step_failed",
        "gate_passed",
        "gate_halted",
        "gate_failed",
        "agent_message",    # User-visible message
        "artifact_registered",
        "ledger_entry_added",
        "ledger_entry_satisfied",
        "ledger_entry_failed",
        "context_violation",
        "drift_detected",
    }

    # Criticality levels
    CRITICALITY = {
        "low": ["ledger_entry_added", "ledger_entry_satisfied", "agent_message"],
        "normal": ["run_started", "run_resumed", "run_succeeded", "step_started", "step_completed", "gate_passed", "artifact_registered"],
        "high": ["step_failed", "gate_failed", "ledger_entry_failed", "context_violation"],
        "critical": ["run_failed", "run_halted", "run_blocked", "step_halted", "gate_halted", "drift_detected"],
    }

    def __init__(self, output_path: Path, observability_mode: str = "full"):
        """
        Initialize telemetry sink (T056).

        Args:
            output_path: Path to JSONL output file
            observability_mode: Observability mode ("minimal", "full", "silent")
        """
        self.output_path = output_path
        self.observability_mode = observability_mode
        self._event_count = 0
        self._allowed_events = ObservabilityMode.get_filtered_events(observability_mode)

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _get_criticality(self, event_type: str) -> str:
        """Get criticality level for event type."""
        for level, types in self.CRITICALITY.items():
            if event_type in types:
                return level
        return "normal"

    def emit(
        self,
        event_type: str,
        run_id: str,
        data: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """
        Emit a telemetry event (T056: respects observability mode).

        Args:
            event_type: Type of event
            run_id: Run identifier
            data: Event-specific data
            step_id: Optional step identifier
            agent_id: Optional agent identifier

        Returns:
            Event ID (may be empty string if event filtered)
        """
        if event_type not in self.EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")

        # T056: Filter events based on observability mode
        if event_type not in self._allowed_events:
            return ""  # Event filtered out

        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        self._event_count += 1

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "run_id": run_id,
            "timestamp": self._now(),
            "criticality": self._get_criticality(event_type),
            "sequence": self._event_count,
        }

        if step_id:
            event["step_id"] = step_id
        if agent_id:
            event["agent_id"] = agent_id
        if data:
            event["data"] = data

        self._write_event(event)
        return event_id

    def _write_event(self, event: Dict[str, Any]) -> None:
        """Write event to JSONL file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "a") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")

    # Convenience methods for common events

    def run_started(self, run_id: str, playbook_id: str) -> str:
        """Emit run_started event."""
        return self.emit("run_started", run_id, {"playbook_id": playbook_id})

    def run_succeeded(self, run_id: str, steps_completed: int, artifacts_count: int = 0) -> str:
        """
        Emit run_succeeded event (terminal success).

        Sprint 9.1: Also emits run_completed for backward compatibility.
        Sprint 9.2: run_completed includes deprecated_alias_of field.
        The run_completed alias will be removed in Sprint 11.
        """
        data = {
            "steps_completed": steps_completed,
            "artifacts_count": artifacts_count,
        }
        # Emit canonical event
        event_id = self.emit("run_succeeded", run_id, data)
        # Emit deprecated alias with marker (Sprint 9.2)
        alias_data = {
            **data,
            "deprecated_alias_of": "run_succeeded",
        }
        self.emit("run_completed", run_id, alias_data)
        return event_id

    def run_failed(self, run_id: str, reason: str, step_id: Optional[str] = None) -> str:
        """Emit run_failed event (terminal failure)."""
        return self.emit("run_failed", run_id, {"reason": reason}, step_id=step_id)

    def run_halted(
        self,
        run_id: str,
        reason: str,
        halt_type: str,
    ) -> str:
        """Emit run_halted event (terminal system halt - not resumable)."""
        return self.emit("run_halted", run_id, {
            "reason": reason,
            "halt_type": halt_type,
        })

    def run_blocked(
        self,
        run_id: str,
        reason: str,
        blocked_at_step: str,
        blocked_at_gate: str,
        missing_inputs: List[str],
        workspace_id: str,
        reason_code: Optional[str] = None,
    ) -> str:
        """
        Emit run_blocked event (terminal but resumable - awaiting user input).

        Sprint 9.2: Added reason_code for machine-readable blocked reasons.
        """
        data = {
            "reason": reason,
            "blocked_at_step": blocked_at_step,
            "blocked_at_gate": blocked_at_gate,
            "missing_inputs": missing_inputs,
            "resume_command": f"processos resume --workspace {workspace_id}",
        }
        if reason_code:
            data["reason_code"] = reason_code
        return self.emit("run_blocked", run_id, data)

    def run_resumed(
        self,
        run_id: str,
        resumed_from_step: str,
        previous_status: str = "blocked",
        from_run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        resume_attempt: Optional[int] = None,
    ) -> str:
        """
        Emit run_resumed event (blocked run continues).

        Sprint 9.1: Includes resume lineage for audit chain.
        """
        data = {
            "resumed_from_step": resumed_from_step,
            "previous_status": previous_status,
        }
        # Sprint 9.1 lineage fields
        if from_run_id is not None:
            data["from_run_id"] = from_run_id
        if parent_run_id is not None:
            data["parent_run_id"] = parent_run_id
        if resume_attempt is not None:
            data["resume_attempt"] = resume_attempt
            data["to_run_id"] = run_id
        return self.emit("run_resumed", run_id, data)

    def agent_message(
        self,
        run_id: str,
        agent_id: str,
        sequence: int,
        level: str,
        message: str,
    ) -> str:
        """Emit agent_message event (user-visible message)."""
        return self.emit("agent_message", run_id, {
            "sequence": sequence,
            "level": level,
            "message": message,
        }, agent_id=agent_id)

    def step_halted(
        self,
        run_id: str,
        step_id: str,
        gate_id: str,
        reason: str,
    ) -> str:
        """Emit step_halted event."""
        return self.emit(
            "step_halted",
            run_id,
            {"gate_id": gate_id, "reason": reason},
            step_id=step_id,
        )

    def gate_halted(
        self,
        run_id: str,
        step_id: str,
        gate_id: str,
        reason: str,
        missing_items: Optional[list] = None,
    ) -> str:
        """Emit gate_halted event (gate requires user input)."""
        data = {"gate_id": gate_id, "reason": reason}
        if missing_items:
            data["missing_items"] = missing_items
        return self.emit("gate_halted", run_id, data, step_id=step_id)

    def drift_detected(
        self,
        run_id: str,
        violation_type: str,
        details: str,
    ) -> str:
        """Emit drift_detected event."""
        return self.emit(
            "drift_detected",
            run_id,
            {"violation_type": violation_type, "details": details},
        )

    def step_started(self, run_id: str, step_id: str, agent_id: str) -> str:
        """Emit step_started event."""
        return self.emit("step_started", run_id, {"agent_id": agent_id}, step_id=step_id, agent_id=agent_id)

    def step_completed(self, run_id: str, step_id: str, artifacts: list) -> str:
        """Emit step_completed event."""
        return self.emit("step_completed", run_id, {"artifact_count": len(artifacts)}, step_id=step_id)

    def step_failed(self, run_id: str, step_id: str, reason: str) -> str:
        """Emit step_failed event."""
        return self.emit("step_failed", run_id, {"reason": reason}, step_id=step_id)

    def gate_passed(self, run_id: str, step_id: str, gate_id: str, reason: str) -> str:
        """Emit gate_passed event."""
        return self.emit("gate_passed", run_id, {"gate_id": gate_id, "reason": reason}, step_id=step_id)

    def gate_failed(self, run_id: str, step_id: str, gate_id: str, reason: str) -> str:
        """Emit gate_failed event."""
        return self.emit("gate_failed", run_id, {"gate_id": gate_id, "reason": reason}, step_id=step_id)

    def artifact_registered(self, run_id: str, step_id: str, artifact_id: str, sha256: str, kind: str) -> str:
        """Emit artifact_registered event."""
        return self.emit(
            "artifact_registered",
            run_id,
            {"artifact_id": artifact_id, "sha256": sha256, "kind": kind},
            step_id=step_id,
        )

    def ledger_entry_added(self, run_id: str, step_id: str, entry_id: str, requirement: str) -> str:
        """Emit ledger_entry_added event."""
        return self.emit(
            "ledger_entry_added",
            run_id,
            {"entry_id": entry_id, "requirement": requirement},
            step_id=step_id,
        )

    def context_violation(self, run_id: str, step_id: str, violation_type: str, details: str) -> str:
        """Emit context_violation event."""
        return self.emit(
            "context_violation",
            run_id,
            {"violation_type": violation_type, "details": details},
            step_id=step_id,
        )


def load_events(path: Path) -> list[Dict[str, Any]]:
    """
    Load events from JSONL file.

    Args:
        path: Path to JSONL file

    Returns:
        List of event dictionaries
    """
    if not path.exists():
        return []

    events = []
    with open(path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def filter_events(events: list, event_type: Optional[str] = None, run_id: Optional[str] = None) -> list:
    """
    Filter events by type and/or run.

    Args:
        events: List of events
        event_type: Filter by event type
        run_id: Filter by run ID

    Returns:
        Filtered list
    """
    result = events
    if event_type:
        result = [e for e in result if e.get("event_type") == event_type]
    if run_id:
        result = [e for e in result if e.get("run_id") == run_id]
    return result
