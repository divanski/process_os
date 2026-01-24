"""
ProcessOS User Stream

Append-only STREAM.md for user-visible agent messages.
Deterministic, auditable, works in both terminal and VSCode modes.

Sprint 9.1: STREAM.md is now fully deterministic:
- No wall-clock timestamps (timestamps remain in telemetry.jsonl)
- Sequence counter is monotonic and deterministic
- Identical inputs produce byte-identical STREAM.md
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .telemetry import TelemetrySink


@dataclass
class StreamEntry:
    """A single entry in the user stream."""

    sequence: int
    agent_id: str
    level: str  # info, warn, error, blocked, success
    message: str

    def to_line(self) -> str:
        """Format as STREAM.md line (deterministic, no timestamp)."""
        seq_str = f"{self.sequence:04d}"
        return f"{seq_str} | {self.agent_id} | {self.level} | {self.message}"


class UserStream:
    """
    Append-only stream for user-visible messages.

    Creates STREAM.md in workspace root with deterministic format:
        TIMESTAMP | SEQ | AGENT_ID | LEVEL | MESSAGE
    """

    VALID_LEVELS = {"info", "warn", "error", "blocked", "success"}
    # Sprint 9.1: No timestamp column - deterministic artifact
    HEADER = "# Run Progress Stream\n\n| Seq | Agent | Level | Message |\n|-----|-------|-------|---------|"

    def __init__(
        self,
        workspace_root: Path,
        run_id: str,
        telemetry: Optional[TelemetrySink] = None,
    ):
        """
        Initialize user stream.

        Args:
            workspace_root: Path to workspace directory
            run_id: Run identifier
            telemetry: Optional telemetry sink for emitting events
        """
        self.workspace_root = Path(workspace_root)
        self.run_id = run_id
        self.telemetry = telemetry
        self.stream_path = self.workspace_root / "STREAM.md"
        self._sequence = 0

        # Initialize stream file if it doesn't exist
        if not self.stream_path.exists():
            self._init_stream()

    def _init_stream(self) -> None:
        """Initialize STREAM.md with header."""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        with open(self.stream_path, "w") as f:
            f.write(self.HEADER + "\n")

    def emit(
        self,
        agent_id: str,
        message: str,
        level: str = "info",
    ) -> StreamEntry:
        """
        Emit a user-visible message.

        Args:
            agent_id: Agent identifier or "system"
            message: Human-readable message (no machine paths, no random IDs)
            level: Message level (info, warn, error, blocked, success)

        Returns:
            StreamEntry that was written
        """
        if level not in self.VALID_LEVELS:
            raise ValueError(f"Invalid level: {level}. Must be one of {self.VALID_LEVELS}")

        self._sequence += 1

        # Sprint 9.1: StreamEntry is deterministic (no timestamp)
        entry = StreamEntry(
            sequence=self._sequence,
            agent_id=agent_id,
            level=level,
            message=message,
        )

        # Append to STREAM.md (atomic-ish: append + fsync)
        self._append_entry(entry)

        # Emit telemetry event
        if self.telemetry:
            self.telemetry.agent_message(
                self.run_id,
                agent_id,
                self._sequence,
                level,
                message,
            )

        return entry

    def _append_entry(self, entry: StreamEntry) -> None:
        """Append entry to STREAM.md with fsync for durability."""
        # Sprint 9.1: No timestamp - deterministic artifact
        line = f"| {entry.sequence:04d} | {entry.agent_id} | {entry.level} | {entry.message} |\n"

        # Open in append mode, write, and fsync
        fd = os.open(str(self.stream_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def info(self, agent_id: str, message: str) -> StreamEntry:
        """Emit info-level message."""
        return self.emit(agent_id, message, "info")

    def warn(self, agent_id: str, message: str) -> StreamEntry:
        """Emit warn-level message."""
        return self.emit(agent_id, message, "warn")

    def error(self, agent_id: str, message: str) -> StreamEntry:
        """Emit error-level message."""
        return self.emit(agent_id, message, "error")

    def blocked(self, agent_id: str, message: str) -> StreamEntry:
        """Emit blocked-level message (awaiting user input)."""
        return self.emit(agent_id, message, "blocked")

    def success(self, agent_id: str, message: str) -> StreamEntry:
        """Emit success-level message."""
        return self.emit(agent_id, message, "success")

    def get_sequence(self) -> int:
        """Get current sequence number."""
        return self._sequence

    def set_sequence(self, seq: int) -> None:
        """Set sequence number (for resume)."""
        self._sequence = seq

    # T058: Enhanced progress output

    def progress(
        self,
        agent_id: str,
        step_name: str,
        current: int,
        total: int,
        message: Optional[str] = None,
    ) -> StreamEntry:
        """
        Emit a progress update with percentage (T058).

        Args:
            agent_id: Agent identifier
            step_name: Name of the current step
            current: Current step number (1-based)
            total: Total number of steps
            message: Optional additional message

        Returns:
            StreamEntry that was written
        """
        percent = int((current / total) * 100) if total > 0 else 0
        progress_bar = self._format_progress_bar(percent)
        base_msg = f"[{current}/{total}] {step_name} {progress_bar}"
        if message:
            base_msg = f"{base_msg} - {message}"
        return self.emit(agent_id, base_msg, "info")

    def _format_progress_bar(self, percent: int, width: int = 20) -> str:
        """Format a text progress bar."""
        filled = int(width * percent / 100)
        empty = width - filled
        return f"[{'=' * filled}{' ' * empty}] {percent}%"

    def step_start(self, agent_id: str, step_name: str, current: int, total: int) -> StreamEntry:
        """Emit step start with progress (T058)."""
        percent = int((current / total) * 100) if total > 0 else 0
        msg = f"Starting step {current}/{total}: {step_name} ({percent}% complete)"
        return self.emit(agent_id, msg, "info")

    def step_complete(self, agent_id: str, step_name: str, current: int, total: int) -> StreamEntry:
        """Emit step completion with progress (T058)."""
        percent = int((current / total) * 100) if total > 0 else 0
        msg = f"Completed step {current}/{total}: {step_name} ({percent}% complete)"
        return self.emit(agent_id, msg, "success")

    def run_summary(self, agent_id: str, steps_completed: int, total_steps: int, artifacts: int = 0) -> StreamEntry:
        """Emit run summary (T058)."""
        percent = int((steps_completed / total_steps) * 100) if total_steps > 0 else 0
        msg = f"Run complete: {steps_completed}/{total_steps} steps ({percent}%)"
        if artifacts > 0:
            msg += f", {artifacts} artifacts generated"
        return self.emit(agent_id, msg, "success")

    def blocked_with_action(
        self,
        agent_id: str,
        reason: str,
        next_action: str,
        workspace_id: Optional[str] = None,
    ) -> StreamEntry:
        """
        Emit blocked message with clear next action (T060).

        Args:
            agent_id: Agent identifier
            reason: Why the run is blocked
            next_action: What the user should do next
            workspace_id: Optional workspace ID for resume command

        Returns:
            StreamEntry that was written
        """
        lines = [f"BLOCKED: {reason}"]
        lines.append(f"Next: {next_action}")
        if workspace_id:
            lines.append(f"Resume: processos resume --workspace {workspace_id}")
        return self.emit(agent_id, " | ".join(lines), "blocked")


def emit_user_message(
    run_id: str,
    workspace_root: Path,
    agent_id: str,
    message: str,
    level: str = "info",
    telemetry: Optional[TelemetrySink] = None,
    sequence: Optional[int] = None,
) -> StreamEntry:
    """
    Convenience function to emit a user message.

    Args:
        run_id: Run identifier
        workspace_root: Path to workspace directory
        agent_id: Agent identifier or "system"
        message: Human-readable message
        level: Message level
        telemetry: Optional telemetry sink
        sequence: Optional sequence number override

    Returns:
        StreamEntry that was written
    """
    stream = UserStream(workspace_root, run_id, telemetry)
    if sequence is not None:
        stream.set_sequence(sequence - 1)  # Will be incremented
    return stream.emit(agent_id, message, level)
