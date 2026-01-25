"""
Operation state management with checkpoint support.

Implements:
- T041: OperationManager class
- T042: Checkpoint storage structure
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class OperationState:
    """
    Represents the state of a long-running operation.

    Tracks progress, current phase, and provides checkpoint capability.
    """

    def __init__(
        self,
        operation_id: str,
        session_id: str,
        description: str,
    ):
        """
        Initialize operation state.

        Args:
            operation_id: Unique operation identifier
            session_id: Associated session ID
            description: Operation description
        """
        self.operation_id = operation_id
        self.session_id = session_id
        self.description = description
        self.status = "pending"  # pending, in_progress, completed, cancelled
        self.phase = "initialization"
        self.progress_percent = 0.0
        self.started_at = datetime.now().isoformat()
        self.last_checkpoint: Optional[str] = None
        self.checkpoints: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "session_id": self.session_id,
            "description": self.description,
            "status": self.status,
            "phase": self.phase,
            "progress_percent": self.progress_percent,
            "started_at": self.started_at,
            "last_checkpoint": self.last_checkpoint,
        }


class Checkpoint:
    """
    Represents a checkpoint of operation state at a point in time.

    Allows resuming operations from checkpoint after interruption.
    """

    def __init__(
        self,
        operation_id: str,
        phase: str,
        progress_percent: float,
        state_data: Dict[str, Any],
    ):
        """
        Initialize checkpoint.

        Args:
            operation_id: Associated operation ID
            phase: Current phase at checkpoint
            progress_percent: Progress percentage at checkpoint
            state_data: State data to preserve
        """
        self.checkpoint_id = str(uuid4())
        self.operation_id = operation_id
        self.timestamp = datetime.now().isoformat()
        self.phase = phase
        self.progress_percent = progress_percent
        self.state_data = state_data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "operation_id": self.operation_id,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "progress_percent": self.progress_percent,
            "state_data": self.state_data,
        }


class OperationManager:
    """
    Manages long-running operations with state tracking and checkpointing.

    Provides:
    - Operation lifecycle management
    - Progress tracking
    - Checkpoint creation and resumption
    - State persistence
    """

    def __init__(self, operations_dir: Optional[Path] = None):
        """
        Initialize OperationManager.

        Args:
            operations_dir: Directory for operation state files
        """
        self.operations_dir = Path(operations_dir) if operations_dir else Path.cwd()
        self.operations: Dict[str, OperationState] = {}

        # Ensure directory exists
        self.operations_dir.mkdir(parents=True, exist_ok=True)

    def create_operation(
        self,
        session_id: str,
        description: str,
    ) -> str:
        """
        Create new operation.

        Args:
            session_id: Associated session ID
            description: Operation description

        Returns:
            Generated operation ID
        """
        operation_id = str(uuid4())

        op_state = OperationState(
            operation_id=operation_id,
            session_id=session_id,
            description=description,
        )

        self.operations[operation_id] = op_state

        # Create operation directory
        op_dir = self.operations_dir / operation_id
        op_dir.mkdir(exist_ok=True)

        # Write initial state
        self._save_operation_state(operation_id)

        return operation_id

    def get_operation(self, operation_id: str) -> Optional[OperationState]:
        """
        Get operation state.

        Args:
            operation_id: Operation identifier

        Returns:
            OperationState or None if not found
        """
        return self.operations.get(operation_id)

    def update_operation_progress(
        self,
        operation_id: str,
        phase: str,
        progress_percent: float,
    ) -> bool:
        """
        Update operation progress.

        Args:
            operation_id: Operation identifier
            phase: Current phase
            progress_percent: Progress percentage (0-100)

        Returns:
            True if updated, False if operation not found
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return False

        op_state.phase = phase
        op_state.progress_percent = min(100.0, max(0.0, progress_percent))

        if op_state.status == "pending":
            op_state.status = "in_progress"

        self._save_operation_state(operation_id)
        return True

    def complete_operation(self, operation_id: str) -> bool:
        """
        Mark operation as completed.

        Args:
            operation_id: Operation identifier

        Returns:
            True if completed, False if not found
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return False

        op_state.status = "completed"
        op_state.phase = "complete"
        op_state.progress_percent = 100.0

        self._save_operation_state(operation_id)
        return True

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        """
        Cancel operation.

        Args:
            operation_id: Operation identifier
            reason: Cancellation reason

        Returns:
            True if cancelled, False if not found
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return False

        op_state.status = "cancelled"

        self._save_operation_state(operation_id)
        return True

    def create_checkpoint(
        self,
        operation_id: str,
        phase: str,
        progress_percent: float,
        state_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        Create checkpoint for operation resumption.

        Args:
            operation_id: Operation identifier
            phase: Current phase
            progress_percent: Current progress
            state_data: State to preserve for resumption

        Returns:
            Checkpoint ID or None if operation not found
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return None

        # Create checkpoint
        checkpoint = Checkpoint(
            operation_id=operation_id,
            phase=phase,
            progress_percent=progress_percent,
            state_data=state_data,
        )

        # Store checkpoint
        op_state.checkpoints.append(checkpoint.to_dict())
        op_state.last_checkpoint = checkpoint.checkpoint_id

        # Write checkpoint to file
        op_dir = self.operations_dir / operation_id
        checkpoint_file = op_dir / f"checkpoint-{checkpoint.checkpoint_id}.json"

        checkpoint_file.write_text(json.dumps(checkpoint.to_dict(), indent=2))

        # Update operation state
        self._save_operation_state(operation_id)

        return checkpoint.checkpoint_id

    def get_last_checkpoint(
        self, operation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get last checkpoint for operation.

        Args:
            operation_id: Operation identifier

        Returns:
            Checkpoint data or None
        """
        op_state = self.get_operation(operation_id)
        if not op_state or not op_state.last_checkpoint:
            return None

        if op_state.checkpoints:
            return op_state.checkpoints[-1]

        return None

    def resume_from_checkpoint(
        self,
        operation_id: str,
        checkpoint_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Resume operation from checkpoint.

        Args:
            operation_id: Operation identifier
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data or None if not found
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return None

        # Find checkpoint
        for checkpoint in op_state.checkpoints:
            if checkpoint["checkpoint_id"] == checkpoint_id:
                # Reset operation to checkpoint state
                op_state.phase = checkpoint["phase"]
                op_state.progress_percent = checkpoint["progress_percent"]
                op_state.status = "in_progress"

                self._save_operation_state(operation_id)

                return checkpoint

        return None

    def get_all_checkpoints(
        self, operation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all checkpoints for operation.

        Args:
            operation_id: Operation identifier

        Returns:
            List of checkpoints
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return []

        return op_state.checkpoints

    def get_operations_for_session(self, session_id: str) -> List[str]:
        """
        Get all operation IDs for session.

        Args:
            session_id: Session identifier

        Returns:
            List of operation IDs
        """
        return [
            op_id
            for op_id, op_state in self.operations.items()
            if op_state.session_id == session_id
        ]

    def get_active_operations(self) -> List[str]:
        """
        Get all active operation IDs.

        Returns:
            List of in_progress operation IDs
        """
        return [
            op_id
            for op_id, op_state in self.operations.items()
            if op_state.status == "in_progress"
        ]

    def _save_operation_state(self, operation_id: str) -> None:
        """
        Save operation state to file.

        Args:
            operation_id: Operation identifier
        """
        op_state = self.get_operation(operation_id)
        if not op_state:
            return

        op_dir = self.operations_dir / operation_id
        op_dir.mkdir(exist_ok=True)

        state_file = op_dir / "state.json"
        state_file.write_text(json.dumps(op_state.to_dict(), indent=2))

    def __repr__(self) -> str:
        """String representation of operation manager."""
        active = len(self.get_active_operations())
        total = len(self.operations)
        return f"OperationManager(active={active}, total={total})"
