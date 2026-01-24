"""
ProcessOS Task Ledger

Append-only checklist of commitments per run.
Steps cannot advance unless all required ledger items are satisfied.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class LedgerEntry:
    """Single entry in the task ledger."""
    entry_id: str
    step_id: str
    requirement: str
    status: str  # pending, satisfied, failed, skipped
    added_at: str
    satisfied_at: Optional[str] = None
    satisfied_by: Optional[str] = None  # SHA256 or gate ID
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "entry_id": self.entry_id,
            "step_id": self.step_id,
            "requirement": self.requirement,
            "status": self.status,
            "added_at": self.added_at,
        }
        if self.satisfied_at:
            result["satisfied_at"] = self.satisfied_at
        if self.satisfied_by:
            result["satisfied_by"] = self.satisfied_by
        if self.failure_reason:
            result["failure_reason"] = self.failure_reason
        return result


class TaskLedger:
    """
    Append-only task ledger for drift prevention.

    Features:
    - Add requirements that must be satisfied
    - Mark requirements as satisfied (with proof)
    - Block step completion until all requirements met
    - Immutable history (append-only)
    """

    def __init__(self, run_id: str, output_path: Optional[Path] = None):
        """
        Initialize ledger for a run.

        Args:
            run_id: Run identifier
            output_path: Path to persist ledger (optional)
        """
        self.run_id = run_id
        self.output_path = output_path
        self._ledger_id = self._generate_ledger_id(run_id)
        self._created_at = datetime.now(timezone.utc).isoformat()
        self._entries: List[LedgerEntry] = []
        self._entry_counter = 0

    def _generate_ledger_id(self, run_id: str) -> str:
        """Generate deterministic ledger ID."""
        hash_hex = hashlib.sha256(run_id.encode()).hexdigest()[:12]
        return f"ledger-{hash_hex}"

    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        self._entry_counter += 1
        data = f"{self._ledger_id}-{self._entry_counter}"
        hash_hex = hashlib.sha256(data.encode()).hexdigest()[:8]
        return f"entry-{hash_hex}"

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def add_requirement(self, step_id: str, requirement: str) -> str:
        """
        Add a requirement to the ledger.

        Args:
            step_id: Step this requirement belongs to
            requirement: Description of what must be satisfied

        Returns:
            Entry ID
        """
        entry = LedgerEntry(
            entry_id=self._generate_entry_id(),
            step_id=step_id,
            requirement=requirement,
            status="pending",
            added_at=self._now(),
        )
        self._entries.append(entry)
        self._persist()
        return entry.entry_id

    def satisfy(self, entry_id: str, satisfied_by: str) -> bool:
        """
        Mark a requirement as satisfied.

        Args:
            entry_id: Entry to satisfy
            satisfied_by: SHA256 or identifier proving satisfaction

        Returns:
            True if satisfied, False if entry not found
        """
        for entry in self._entries:
            if entry.entry_id == entry_id and entry.status == "pending":
                entry.status = "satisfied"
                entry.satisfied_at = self._now()
                entry.satisfied_by = satisfied_by
                self._persist()
                return True
        return False

    def fail(self, entry_id: str, reason: str) -> bool:
        """
        Mark a requirement as failed.

        Args:
            entry_id: Entry that failed
            reason: Failure reason

        Returns:
            True if marked, False if entry not found
        """
        for entry in self._entries:
            if entry.entry_id == entry_id and entry.status == "pending":
                entry.status = "failed"
                entry.failure_reason = reason
                self._persist()
                return True
        return False

    def skip(self, entry_id: str, reason: str) -> bool:
        """
        Mark a requirement as skipped.

        Args:
            entry_id: Entry to skip
            reason: Skip reason

        Returns:
            True if skipped, False if entry not found
        """
        for entry in self._entries:
            if entry.entry_id == entry_id and entry.status == "pending":
                entry.status = "skipped"
                entry.failure_reason = reason
                self._persist()
                return True
        return False

    def can_proceed(self, step_id: str) -> tuple[bool, List[str]]:
        """
        Check if step can proceed (all requirements satisfied).

        Args:
            step_id: Step to check

        Returns:
            Tuple of (can_proceed, list of blocking requirement descriptions)
        """
        blocking = []
        for entry in self._entries:
            if entry.step_id == step_id:
                if entry.status == "pending":
                    blocking.append(entry.requirement)
                elif entry.status == "failed":
                    blocking.append(f"FAILED: {entry.requirement} - {entry.failure_reason}")

        return len(blocking) == 0, blocking

    def get_step_entries(self, step_id: str) -> List[LedgerEntry]:
        """Get all entries for a step."""
        return [e for e in self._entries if e.step_id == step_id]

    def get_pending(self) -> List[LedgerEntry]:
        """Get all pending entries."""
        return [e for e in self._entries if e.status == "pending"]

    def get_failed(self) -> List[LedgerEntry]:
        """Get all failed entries."""
        return [e for e in self._entries if e.status == "failed"]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ledger to dictionary."""
        return {
            "ledger_id": self._ledger_id,
            "run_id": self.run_id,
            "created_at": self._created_at,
            "entries": [e.to_dict() for e in self._entries],
        }

    def _persist(self) -> None:
        """Persist ledger to disk if output path set."""
        if self.output_path:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(
                json.dumps(self.to_dict(), sort_keys=True, indent=2)
            )

    @classmethod
    def load(cls, path: Path) -> "TaskLedger":
        """Load ledger from disk."""
        data = json.loads(path.read_text())
        ledger = cls(data["run_id"], path)
        ledger._ledger_id = data["ledger_id"]
        ledger._created_at = data["created_at"]
        ledger._entries = [
            LedgerEntry(**entry) for entry in data["entries"]
        ]
        ledger._entry_counter = len(ledger._entries)
        return ledger
