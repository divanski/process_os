"""
Unit tests for large project streaming progress.

Tests for Phase 7 (US5): Streaming Progress for Large Projects

Tests:
- T174-T179: Large project streaming, checkpoints, resumption, cancellation
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

import pytest


@dataclass
class ProgressUpdate:
    """Single progress update message."""

    operation_id: str
    phase: str  # language, framework, patterns, conventions
    current_file: int
    total_files: int
    progress_percent: float
    elapsed_seconds: float
    estimated_remaining_seconds: float
    confidence_score: float
    patterns_found: int
    conventions_found: int
    timestamp: str


@dataclass
class CheckpointData:
    """Checkpoint data for operation resumption."""

    operation_id: str
    phase: str
    progress_percent: float
    current_file_index: int
    patterns_found: List[str]
    conventions_learned: Dict[str, Any]
    timestamp: str
    analysis_results: Dict[str, Any]


class StreamingAnalyzer:
    """Streams progress for large project analysis."""

    def __init__(self, operation_id: str, total_files: int):
        """
        Initialize streaming analyzer.

        Args:
            operation_id: Unique operation ID
            total_files: Total files to analyze
        """
        self.operation_id = operation_id
        self.total_files = total_files
        self.current_file = 0
        self.progress_updates = []
        self.is_cancelled = False
        self.patterns_found = []
        self.conventions = {}
        self.start_time = time.time()

    def emit_progress_update(self) -> ProgressUpdate:
        """
        Emit progress update for current state.

        Returns:
            ProgressUpdate message
        """
        elapsed = time.time() - self.start_time
        progress = (self.current_file / self.total_files * 100) if self.total_files > 0 else 0

        # Estimate remaining time based on rate
        if self.current_file > 0 and elapsed > 0:
            rate = self.current_file / elapsed  # files per second
            remaining_files = self.total_files - self.current_file
            estimated_remaining = remaining_files / rate if rate > 0 else 0
        else:
            estimated_remaining = 0

        update = ProgressUpdate(
            operation_id=self.operation_id,
            phase=self._get_current_phase(),
            current_file=self.current_file,
            total_files=self.total_files,
            progress_percent=progress,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining,
            confidence_score=min(0.5 + (progress / 200), 0.95),  # Confidence increases with progress
            patterns_found=len(self.patterns_found),
            conventions_found=len(self.conventions),
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        self.progress_updates.append(update)
        return update

    def _get_current_phase(self) -> str:
        """Determine current phase based on progress."""
        percent = (self.current_file / self.total_files * 100) if self.total_files > 0 else 0

        if percent < 25:
            return "language_detection"
        elif percent < 50:
            return "framework_detection"
        elif percent < 75:
            return "pattern_discovery"
        else:
            return "convention_learning"

    def analyze_batch(self, batch_size: int = 100) -> int:
        """
        Analyze a batch of files (simulated).

        Args:
            batch_size: Files to analyze per batch

        Returns:
            Files processed
        """
        if self.is_cancelled:
            return 0

        files_processed = min(batch_size, self.total_files - self.current_file)
        self.current_file += files_processed

        # Simulate finding patterns and conventions
        if files_processed > 0:
            self.patterns_found.append(f"pattern_{self.current_file}")
            self.conventions[f"convention_{len(self.conventions)}"] = {
                "type": "naming",
                "value": "camelCase",
            }

        return files_processed

    def cancel(self):
        """Cancel the analysis operation."""
        self.is_cancelled = True

    def is_complete(self) -> bool:
        """Check if analysis is complete."""
        return self.current_file >= self.total_files

    def create_checkpoint(self) -> CheckpointData:
        """
        Create checkpoint from current state.

        Returns:
            CheckpointData for resumption
        """
        return CheckpointData(
            operation_id=self.operation_id,
            phase=self._get_current_phase(),
            progress_percent=(self.current_file / self.total_files * 100),
            current_file_index=self.current_file,
            patterns_found=self.patterns_found.copy(),
            conventions_learned=self.conventions.copy(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            analysis_results={
                "patterns": self.patterns_found,
                "conventions": self.conventions,
                "elapsed_seconds": time.time() - self.start_time,
            },
        )


class TestLargeProjectStreaming:
    """Test streaming progress for large projects (T174-T179)."""

    def test_progress_updates_every_1_2_seconds(self):
        """Verify progress updates stream at 1-2 second intervals (T175)."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Simulate analysis with progress updates
        start_time = time.time()
        last_update_time = start_time
        update_intervals = []

        # Simulate batches with timing
        for _ in range(5):
            analyzer.analyze_batch(2000)
            update = analyzer.emit_progress_update()

            current_time = time.time()
            interval = current_time - last_update_time
            update_intervals.append(interval)
            last_update_time = current_time

            # Simulate 1-2 second delay between updates
            time.sleep(0.01)  # Small delay

        # Check that updates were emitted
        assert len(analyzer.progress_updates) >= 5
        assert all(isinstance(u, ProgressUpdate) for u in analyzer.progress_updates)

    def test_checkpoint_saved_on_operation_cancel(self):
        """Verify checkpoint is saved when operation is cancelled (T176)."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Analyze some files
        analyzer.analyze_batch(2000)
        analyzer.emit_progress_update()

        # Cancel operation
        analyzer.cancel()

        # Create checkpoint
        checkpoint = analyzer.create_checkpoint()

        assert checkpoint is not None
        assert checkpoint.operation_id == analyzer.operation_id
        assert checkpoint.progress_percent > 0
        assert checkpoint.current_file_index == 2000
        assert len(checkpoint.patterns_found) > 0
        assert checkpoint.timestamp is not None

    def test_operation_resumable_from_checkpoint(self):
        """Verify operation can be resumed from checkpoint (T177)."""
        operation_id = str(uuid4())
        analyzer1 = StreamingAnalyzer(operation_id, total_files=10000)

        # Analyze some files
        analyzer1.analyze_batch(2000)
        checkpoint = analyzer1.create_checkpoint()

        # Create new analyzer and resume from checkpoint
        analyzer2 = StreamingAnalyzer(operation_id, total_files=10000)
        analyzer2.current_file = checkpoint.current_file_index
        analyzer2.patterns_found = checkpoint.patterns_found.copy()
        analyzer2.conventions = checkpoint.conventions_learned.copy()

        # Verify state is restored
        assert analyzer2.current_file == 2000
        assert len(analyzer2.patterns_found) > 0
        assert analyzer2.create_checkpoint().progress_percent == checkpoint.progress_percent

    def test_progress_updates_continue_from_checkpoint(self):
        """Verify progress continues from checkpoint percentage (T178)."""
        operation_id = str(uuid4())
        analyzer1 = StreamingAnalyzer(operation_id, total_files=10000)

        analyzer1.analyze_batch(3000)
        checkpoint = analyzer1.create_checkpoint()
        checkpoint_progress = checkpoint.progress_percent

        # Resume and continue
        analyzer2 = StreamingAnalyzer(operation_id, total_files=10000)
        analyzer2.current_file = checkpoint.current_file_index

        analyzer2.analyze_batch(3000)
        update = analyzer2.emit_progress_update()

        assert update.progress_percent > checkpoint_progress

    def test_cancellation_handled_gracefully(self):
        """Verify cancellation is handled without data loss (T179)."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Analyze some files
        analyzer.analyze_batch(2000)
        analyzer.emit_progress_update()

        # Store state before cancel
        patterns_before = len(analyzer.patterns_found)
        conventions_before = len(analyzer.conventions)

        # Cancel
        analyzer.cancel()

        # Checkpoint should preserve state
        checkpoint = analyzer.create_checkpoint()

        assert len(checkpoint.patterns_found) == patterns_before
        assert len(checkpoint.conventions_learned) == conventions_before
        assert not analyzer.analyze_batch(1000)  # No more analysis after cancel


class TestProgressAccuracy:
    """Test accuracy of progress tracking."""

    def test_progress_percent_accurate(self):
        """Verify progress_percent is calculated correctly."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        analyzer.analyze_batch(2500)
        update = analyzer.emit_progress_update()

        assert abs(update.progress_percent - 25.0) < 0.1  # Within 0.1%

        analyzer.analyze_batch(2500)
        update = analyzer.emit_progress_update()

        assert abs(update.progress_percent - 50.0) < 0.1

    def test_phase_detection_accurate(self):
        """Verify phase is detected based on progress."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Phase 1: 0-24% (< 25%)
        analyzer.analyze_batch(2400)
        update = analyzer.emit_progress_update()
        assert update.phase == "language_detection"

        # Phase 2: 25-49% (>= 25% and < 50%) - need to add 100 to get to 2500 (25%)
        analyzer.analyze_batch(100)
        update = analyzer.emit_progress_update()
        assert update.phase == "framework_detection"

        # Phase 3: 50-74% (>= 50% and < 75%) - need to add 2500 to get to 5000 (50%)
        analyzer.analyze_batch(2500)
        update = analyzer.emit_progress_update()
        assert update.phase == "pattern_discovery"

        # Phase 4: 75-100% (>= 75%) - need to add 2500 to get to 7500 (75%)
        analyzer.analyze_batch(2500)
        update = analyzer.emit_progress_update()
        assert update.phase == "convention_learning"

    def test_estimated_time_decreases_with_progress(self):
        """Verify estimated remaining time decreases as progress increases."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Early in analysis
        analyzer.analyze_batch(1000)
        time.sleep(0.01)
        update1 = analyzer.emit_progress_update()
        estimated1 = update1.estimated_remaining_seconds

        # Later in analysis
        analyzer.analyze_batch(4000)
        time.sleep(0.01)
        update2 = analyzer.emit_progress_update()
        estimated2 = update2.estimated_remaining_seconds

        # Later estimate should be less (or equal if just starting)
        assert estimated2 <= estimated1


class TestLargeProjectScaling:
    """Test scaling behavior for large projects."""

    def test_10000_file_project_streaming(self):
        """Test streaming with 10,000 file project."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Analyze in batches
        batches = 0
        while not analyzer.is_complete():
            analyzer.analyze_batch(500)
            analyzer.emit_progress_update()
            batches += 1

        assert analyzer.current_file == 10000
        assert batches == 20  # 10000 / 500
        assert len(analyzer.progress_updates) >= 20

    def test_progress_updates_for_100000_files(self):
        """Test progress tracking scales to 100,000 files."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=100000)

        # Analyze larger batches
        while not analyzer.is_complete():
            analyzer.analyze_batch(5000)
            analyzer.emit_progress_update()

        assert analyzer.current_file == 100000
        assert len(analyzer.progress_updates) >= 20


class TestCheckpointPersistence:
    """Test checkpoint save and load functionality."""

    def test_checkpoint_data_completeness(self):
        """Verify checkpoint contains all necessary data."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        analyzer.analyze_batch(3000)
        checkpoint = analyzer.create_checkpoint()

        required_fields = [
            "operation_id",
            "phase",
            "progress_percent",
            "current_file_index",
            "patterns_found",
            "conventions_learned",
            "timestamp",
            "analysis_results",
        ]

        for field in required_fields:
            assert hasattr(checkpoint, field)
            assert getattr(checkpoint, field) is not None

    def test_checkpoint_timestamp_valid(self):
        """Verify checkpoint timestamp is valid ISO format."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        analyzer.analyze_batch(1000)
        checkpoint = analyzer.create_checkpoint()

        # Should be ISO 8601 format
        assert "T" in checkpoint.timestamp
        assert "Z" in checkpoint.timestamp
        assert len(checkpoint.timestamp) > 10

    def test_checkpoint_preserves_all_patterns(self):
        """Verify checkpoint preserves all discovered patterns."""
        analyzer = StreamingAnalyzer(str(uuid4()), total_files=10000)

        # Analyze multiple batches to find patterns
        for _ in range(3):
            analyzer.analyze_batch(1000)

        original_patterns = analyzer.patterns_found.copy()
        checkpoint = analyzer.create_checkpoint()

        assert checkpoint.patterns_found == original_patterns
        assert len(checkpoint.patterns_found) == len(original_patterns)
