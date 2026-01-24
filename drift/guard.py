"""
ProcessOS Drift Guard

Enforces write allowlist and policy compliance during execution.
"""

import fnmatch
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class DriftViolationError(Exception):
    """Raised when execution drifts from approved contracts."""

    def __init__(
        self,
        violation_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.violation_type = violation_type
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "violation_type": self.violation_type,
            "message": str(self),
            "details": self.details,
            "timestamp": self.timestamp,
        }


class WriteViolation(DriftViolationError):
    """Raised when attempting to write outside allowlist."""

    def __init__(self, path: Path, allowlist: List[str]):
        super().__init__(
            violation_type="write_violation",
            message=f"Write to '{path}' blocked: not in allowlist {allowlist}",
            details={"path": str(path), "allowlist": allowlist},
        )


class GateViolation(DriftViolationError):
    """Raised when a gate check fails."""

    def __init__(self, gate_id: str, reason: str):
        super().__init__(
            violation_type="gate_failure",
            message=f"Gate '{gate_id}' failed: {reason}",
            details={"gate_id": gate_id, "reason": reason},
        )


@dataclass
class DriftEvent:
    """Record of a drift check or violation."""

    event_type: str  # "check_passed", "violation_detected"
    check_type: str  # "write", "gate"
    path_or_gate: str
    allowed: bool
    timestamp: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "check_type": self.check_type,
            "path_or_gate": self.path_or_gate,
            "allowed": self.allowed,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class DriftGuard:
    """
    Enforces write allowlist and policy compliance.

    All writes must be within the allowlist patterns.
    Gate failures result in immediate halt.
    """

    def __init__(
        self,
        host_root: Path,
        allowlist: Optional[List[str]] = None,
    ):
        """
        Initialize drift guard.

        Args:
            host_root: Root path of the host project
            allowlist: List of allowed write patterns (default: [".processos/**"])
        """
        self.host_root = Path(host_root).resolve()
        self.allowlist = allowlist or [".processos/**"]
        self._events: List[DriftEvent] = []

    def check_write(self, path: Path) -> None:
        """
        Check if a write to path is allowed.

        Args:
            path: Path to check

        Raises:
            WriteViolation: If path is not in allowlist
        """
        path = Path(path)

        # Make path relative to host_root for pattern matching
        try:
            if path.is_absolute():
                rel_path = path.relative_to(self.host_root)
            else:
                rel_path = path
        except ValueError:
            # Path is outside host_root entirely
            self._record_violation("write", str(path))
            raise WriteViolation(path, self.allowlist)

        rel_str = str(rel_path).replace("\\", "/")

        # Check against allowlist patterns
        for pattern in self.allowlist:
            if fnmatch.fnmatch(rel_str, pattern):
                self._record_check("write", rel_str, allowed=True)
                return

            # Also check if path is under a directory pattern
            if pattern.endswith("/**"):
                dir_pattern = pattern[:-3]
                if rel_str.startswith(dir_pattern + "/") or rel_str == dir_pattern:
                    self._record_check("write", rel_str, allowed=True)
                    return

        # Not allowed
        self._record_violation("write", rel_str)
        raise WriteViolation(path, self.allowlist)

    def check_gate(self, gate_id: str, passed: bool, reason: str = "") -> None:
        """
        Check gate result and halt if failed.

        Args:
            gate_id: Identifier of the gate
            passed: Whether the gate passed
            reason: Reason for failure (if failed)

        Raises:
            GateViolation: If gate failed
        """
        if passed:
            self._record_check("gate", gate_id, allowed=True)
            return

        self._record_violation("gate", gate_id, {"reason": reason})
        raise GateViolation(gate_id, reason)

    def is_path_allowed(self, path: Path) -> bool:
        """
        Check if path is allowed without raising.

        Args:
            path: Path to check

        Returns:
            True if allowed, False otherwise
        """
        try:
            self.check_write(path)
            return True
        except WriteViolation:
            return False

    def get_events(self) -> List[DriftEvent]:
        """Get all recorded drift events."""
        return list(self._events)

    def get_violations(self) -> List[DriftEvent]:
        """Get only violation events."""
        return [e for e in self._events if e.event_type == "violation_detected"]

    def clear_events(self) -> None:
        """Clear recorded events."""
        self._events = []

    def _record_check(
        self,
        check_type: str,
        path_or_gate: str,
        allowed: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a drift check event."""
        self._events.append(
            DriftEvent(
                event_type="check_passed" if allowed else "violation_detected",
                check_type=check_type,
                path_or_gate=path_or_gate,
                allowed=allowed,
                details=details or {},
            )
        )

    def _record_violation(
        self,
        check_type: str,
        path_or_gate: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a violation event."""
        self._record_check(check_type, path_or_gate, allowed=False, details=details)


def create_drift_guard(
    host_root: Path,
    policies: Optional[Dict[str, Any]] = None,
) -> DriftGuard:
    """
    Create a drift guard from policies.

    Args:
        host_root: Root path of host project
        policies: Policy dict with optional "write_allowlist" key

    Returns:
        Configured DriftGuard
    """
    allowlist = None
    if policies:
        allowlist = policies.get("write_allowlist")

    return DriftGuard(host_root=host_root, allowlist=allowlist)
