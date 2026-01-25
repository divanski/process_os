"""
Checkpoint management for large project analysis operations.

Enables saving and resuming analysis of large projects without losing progress.
Checkpoints capture analysis state at cancellation and allow resumption from that point.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class CheckpointData:
    """Complete checkpoint state for resuming analysis."""

    operation_id: str
    phase: str  # language_detection, framework_detection, pattern_discovery, convention_learning
    progress_percent: float  # 0.0-100.0
    current_file_index: int  # Files analyzed so far
    total_files: int  # Total files in project
    patterns_found: List[str]  # Discovered patterns
    conventions_learned: Dict[str, Any]  # Discovered conventions
    timestamp: str  # When checkpoint was created (ISO 8601)
    analysis_results: Dict[str, Any]  # Complete analysis results
    elapsed_seconds: float  # Time spent so far
    reason: Optional[str] = None  # Reason for checkpoint (e.g., "user_cancelled")


class CheckpointManager:
    """
    Manages checkpoint save/load/resume for large project analysis.

    Stores checkpoints in .processos/operations/{operation_id}/checkpoints/
    Enables resuming analysis without re-analyzing previous phases.
    """

    CHECKPOINT_DIR = ".processos/operations"
    CHECKPOINT_FILENAME = "checkpoint.json"
    INDEX_FILENAME = "checkpoint_index.json"

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize checkpoint manager.

        Args:
            base_dir: Base directory for checkpoint storage (default: current directory)
        """
        self.base_dir = Path(base_dir or ".")
        self.checkpoints = {}

    def save_checkpoint(
        self,
        operation_id: str,
        checkpoint: CheckpointData,
    ) -> str:
        """
        Save checkpoint to disk.

        Args:
            operation_id: Unique operation ID
            checkpoint: Checkpoint data to save

        Returns:
            Path to saved checkpoint file
        """
        checkpoint_dir = self._get_checkpoint_dir(operation_id)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Save checkpoint data
        checkpoint_file = checkpoint_dir / self.CHECKPOINT_FILENAME
        checkpoint_dict = asdict(checkpoint)

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_dict, f, indent=2)

        # Update index
        self._update_checkpoint_index(operation_id, checkpoint)

        # Cache in memory
        self.checkpoints[operation_id] = checkpoint

        return str(checkpoint_file)

    def load_checkpoint(self, operation_id: str) -> Optional[CheckpointData]:
        """
        Load checkpoint from disk.

        Args:
            operation_id: Unique operation ID

        Returns:
            CheckpointData if exists, None otherwise
        """
        # Try memory cache first
        if operation_id in self.checkpoints:
            return self.checkpoints[operation_id]

        checkpoint_file = self._get_checkpoint_dir(operation_id) / self.CHECKPOINT_FILENAME

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r") as f:
                data = json.load(f)

            checkpoint = CheckpointData(**data)
            self.checkpoints[operation_id] = checkpoint
            return checkpoint
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def checkpoint_exists(self, operation_id: str) -> bool:
        """
        Check if checkpoint exists for operation.

        Args:
            operation_id: Unique operation ID

        Returns:
            True if checkpoint exists
        """
        if operation_id in self.checkpoints:
            return True

        checkpoint_file = self._get_checkpoint_dir(operation_id) / self.CHECKPOINT_FILENAME
        return checkpoint_file.exists()

    def delete_checkpoint(self, operation_id: str) -> bool:
        """
        Delete checkpoint for completed operation.

        Args:
            operation_id: Unique operation ID

        Returns:
            True if deleted successfully
        """
        checkpoint_dir = self._get_checkpoint_dir(operation_id)

        if not checkpoint_dir.exists():
            return False

        try:
            # Delete checkpoint file
            checkpoint_file = checkpoint_dir / self.CHECKPOINT_FILENAME
            if checkpoint_file.exists():
                checkpoint_file.unlink()

            # Delete directory if empty
            if not any(checkpoint_dir.iterdir()):
                checkpoint_dir.rmdir()

            # Remove from cache
            if operation_id in self.checkpoints:
                del self.checkpoints[operation_id]

            return True
        except OSError:
            return False

    def create_checkpoint(
        self,
        operation_id: str,
        phase: str,
        current_file_index: int,
        total_files: int,
        patterns_found: List[str],
        conventions_learned: Dict[str, Any],
        analysis_results: Dict[str, Any],
        elapsed_seconds: float,
        reason: Optional[str] = None,
    ) -> CheckpointData:
        """
        Create checkpoint from current analysis state.

        Args:
            operation_id: Unique operation ID
            phase: Current analysis phase
            current_file_index: Files analyzed so far
            total_files: Total files in project
            patterns_found: Discovered patterns
            conventions_learned: Discovered conventions
            analysis_results: Complete analysis results
            elapsed_seconds: Time spent so far
            reason: Optional reason for checkpoint

        Returns:
            Created CheckpointData
        """
        progress = (current_file_index / total_files * 100) if total_files > 0 else 0

        checkpoint = CheckpointData(
            operation_id=operation_id,
            phase=phase,
            progress_percent=progress,
            current_file_index=current_file_index,
            total_files=total_files,
            patterns_found=patterns_found.copy(),
            conventions_learned=conventions_learned.copy(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            analysis_results=analysis_results.copy(),
            elapsed_seconds=elapsed_seconds,
            reason=reason,
        )

        return checkpoint

    def list_checkpoints(self) -> Dict[str, CheckpointData]:
        """
        List all available checkpoints.

        Returns:
            Dict mapping operation_id to CheckpointData
        """
        checkpoints = {}
        ops_dir = self.base_dir / self.CHECKPOINT_DIR

        if not ops_dir.exists():
            return checkpoints

        for op_dir in ops_dir.iterdir():
            if op_dir.is_dir():
                operation_id = op_dir.name
                checkpoint = self.load_checkpoint(operation_id)
                if checkpoint:
                    checkpoints[operation_id] = checkpoint

        return checkpoints

    def cleanup_old_checkpoints(self, days_old: int = 7) -> int:
        """
        Clean up checkpoints older than specified days.

        Args:
            days_old: Checkpoints older than this many days will be deleted

        Returns:
            Number of checkpoints deleted
        """
        import time

        checkpoints = self.list_checkpoints()
        deleted = 0
        cutoff_timestamp = datetime.utcnow().timestamp() - (days_old * 86400)

        for operation_id, checkpoint in checkpoints.items():
            checkpoint_time = datetime.fromisoformat(checkpoint.timestamp.rstrip("Z")).timestamp()

            if checkpoint_time < cutoff_timestamp:
                if self.delete_checkpoint(operation_id):
                    deleted += 1

        return deleted

    def _get_checkpoint_dir(self, operation_id: str) -> Path:
        """Get checkpoint directory for operation."""
        return self.base_dir / self.CHECKPOINT_DIR / operation_id / "checkpoints"

    def _update_checkpoint_index(self, operation_id: str, checkpoint: CheckpointData):
        """Update global checkpoint index."""
        ops_dir = self.base_dir / self.CHECKPOINT_DIR
        index_file = ops_dir / self.INDEX_FILENAME

        try:
            # Load existing index
            index = {}
            if index_file.exists():
                with open(index_file, "r") as f:
                    index = json.load(f)

            # Update with new checkpoint
            index[operation_id] = {
                "timestamp": checkpoint.timestamp,
                "phase": checkpoint.phase,
                "progress_percent": checkpoint.progress_percent,
                "reason": checkpoint.reason,
            }

            # Save updated index
            ops_dir.mkdir(parents=True, exist_ok=True)
            with open(index_file, "w") as f:
                json.dump(index, f, indent=2)
        except (OSError, json.JSONDecodeError):
            pass  # Silently fail if index update fails


class CheckpointedAnalyzer:
    """
    Analyzer that supports checkpointing and resumption.

    Wraps the analysis process to enable saving/resuming from checkpoints.
    """

    def __init__(
        self,
        operation_id: str,
        total_files: int,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        """
        Initialize checkpointed analyzer.

        Args:
            operation_id: Unique operation ID
            total_files: Total files to analyze
            checkpoint_manager: Optional checkpoint manager instance
        """
        self.operation_id = operation_id
        self.total_files = total_files
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

        # Analysis state
        self.current_file_index = 0
        self.phase = "language_detection"
        self.patterns_found = []
        self.conventions = {}
        self.analysis_results = {}
        self.is_cancelled = False
        self.start_time = None
        self.elapsed_seconds = 0.0

        # Try to load existing checkpoint
        self._load_checkpoint_if_exists()

    def _load_checkpoint_if_exists(self):
        """Load checkpoint if one exists for this operation."""
        checkpoint = self.checkpoint_manager.load_checkpoint(self.operation_id)

        if checkpoint:
            self.current_file_index = checkpoint.current_file_index
            self.phase = checkpoint.phase
            self.patterns_found = checkpoint.patterns_found.copy()
            self.conventions = checkpoint.conventions_learned.copy()
            self.analysis_results = checkpoint.analysis_results.copy()
            self.elapsed_seconds = checkpoint.elapsed_seconds

    def analyze_files(self, count: int) -> int:
        """
        Analyze files and update state.

        Args:
            count: Number of files to analyze

        Returns:
            Files analyzed
        """
        if self.is_cancelled:
            return 0

        analyzed = min(count, self.total_files - self.current_file_index)
        self.current_file_index += analyzed

        # Update phase based on progress
        self._update_phase()

        # Simulate finding patterns and conventions
        if analyzed > 0:
            self.patterns_found.append(f"pattern_{self.current_file_index}")
            self.conventions[f"conv_{len(self.conventions)}"] = {
                "type": "naming",
                "value": "camelCase",
            }

        return analyzed

    def _update_phase(self):
        """Update phase based on current progress."""
        progress = (self.current_file_index / self.total_files * 100) if self.total_files > 0 else 0

        if progress < 25:
            self.phase = "language_detection"
        elif progress < 50:
            self.phase = "framework_detection"
        elif progress < 75:
            self.phase = "pattern_discovery"
        else:
            self.phase = "convention_learning"

    def cancel(self) -> str:
        """
        Cancel analysis and create checkpoint.

        Returns:
            Path to saved checkpoint
        """
        self.is_cancelled = True

        checkpoint = self.checkpoint_manager.create_checkpoint(
            operation_id=self.operation_id,
            phase=self.phase,
            current_file_index=self.current_file_index,
            total_files=self.total_files,
            patterns_found=self.patterns_found,
            conventions_learned=self.conventions,
            analysis_results=self.analysis_results,
            elapsed_seconds=self.elapsed_seconds,
            reason="user_cancelled",
        )

        return self.checkpoint_manager.save_checkpoint(self.operation_id, checkpoint)

    def complete(self) -> bool:
        """
        Check if analysis is complete.

        Returns:
            True if all files analyzed
        """
        return self.current_file_index >= self.total_files

    def get_checkpoint(self) -> Optional[CheckpointData]:
        """Get current checkpoint."""
        return self.checkpoint_manager.load_checkpoint(self.operation_id)
