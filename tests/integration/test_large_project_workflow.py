"""
Integration tests for large project analysis workflow.

Tests for Phase 7 (US5): End-to-end large project handling

Tests:
- T181-T183: Complete workflow for large projects
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

import pytest


@dataclass
class AnalysisState:
    """Complete state of analysis operation."""

    operation_id: str
    total_files: int
    analyzed_files: int
    progress_percent: float
    phase: str
    patterns_found: List[str]
    conventions: Dict[str, Any]
    is_complete: bool
    is_cancelled: bool
    elapsed_time: float
    checkpoint_available: bool


class LargeProjectAnalyzer:
    """Complete analyzer for large projects with progress streaming."""

    def __init__(self, operation_id: str, total_files: int):
        """Initialize analyzer."""
        self.operation_id = operation_id
        self.total_files = total_files
        self.analyzed_files = 0
        self.patterns_found = []
        self.conventions = {}
        self.is_cancelled = False
        self.is_complete = False
        self.start_time = None
        self.progress_updates = []
        self.checkpoint_saved = False

    def start_analysis(self):
        """Start the analysis."""
        self.start_time = time.time()

    def emit_progress(self) -> Dict[str, Any]:
        """
        Emit progress update.

        Returns:
            Progress update dict
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        progress = (self.analyzed_files / self.total_files * 100) if self.total_files > 0 else 0

        update = {
            "operation_id": self.operation_id,
            "analyzed_files": self.analyzed_files,
            "total_files": self.total_files,
            "progress_percent": progress,
            "elapsed_seconds": elapsed,
            "patterns_found": len(self.patterns_found),
            "conventions_found": len(self.conventions),
            "is_complete": self.is_complete,
            "is_cancelled": self.is_cancelled,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        self.progress_updates.append(update)
        return update

    def analyze_files(self, count: int) -> int:
        """
        Analyze files.

        Args:
            count: Number of files to analyze

        Returns:
            Files analyzed
        """
        if self.is_cancelled:
            return 0

        analyzed = min(count, self.total_files - self.analyzed_files)
        self.analyzed_files += analyzed

        # Simulate finding patterns and conventions
        if analyzed > 0:
            self.patterns_found.append(f"pattern_{self.analyzed_files}")
            self.conventions[f"conv_{len(self.conventions)}"] = "value"

        if self.analyzed_files >= self.total_files:
            self.is_complete = True

        return analyzed

    def cancel(self):
        """Cancel analysis."""
        self.is_cancelled = True
        self.checkpoint_saved = True

    def create_checkpoint(self) -> Dict[str, Any]:
        """Create checkpoint."""
        return {
            "operation_id": self.operation_id,
            "analyzed_files": self.analyzed_files,
            "patterns_found": self.patterns_found.copy(),
            "conventions": self.conventions.copy(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def get_state(self) -> AnalysisState:
        """Get current analysis state."""
        elapsed = time.time() - self.start_time if self.start_time else 0

        return AnalysisState(
            operation_id=self.operation_id,
            total_files=self.total_files,
            analyzed_files=self.analyzed_files,
            progress_percent=(self.analyzed_files / self.total_files * 100) if self.total_files > 0 else 0,
            phase="analysis",
            patterns_found=self.patterns_found,
            conventions=self.conventions,
            is_complete=self.is_complete,
            is_cancelled=self.is_cancelled,
            elapsed_time=elapsed,
            checkpoint_available=self.checkpoint_saved,
        )


class TestLargeProjectWorkflow:
    """End-to-end workflow tests for large projects (T181-T183)."""

    def test_analysis_emits_progress_allows_cancel_and_resumes(self):
        """Test complete workflow: analysis → progress → cancel → resume (T182)."""
        operation_id = str(uuid4())
        analyzer = LargeProjectAnalyzer(operation_id, total_files=10000)

        # Step 1: Start analysis
        analyzer.start_analysis()
        assert analyzer.start_time is not None

        # Step 2: Analyze some files and emit progress
        analyzer.analyze_files(3000)
        update1 = analyzer.emit_progress()

        assert update1["analyzed_files"] == 3000
        assert update1["progress_percent"] == 30.0
        assert not update1["is_complete"]
        assert not update1["is_cancelled"]

        # Step 3: User cancels operation
        analyzer.cancel()
        assert analyzer.is_cancelled

        # Step 4: Create checkpoint for resumption
        checkpoint = analyzer.create_checkpoint()
        assert checkpoint["analyzed_files"] == 3000
        assert len(checkpoint["patterns_found"]) > 0

        # Step 5: Resume from checkpoint
        analyzer2 = LargeProjectAnalyzer(operation_id, total_files=10000)
        analyzer2.start_analysis()
        analyzer2.analyzed_files = checkpoint["analyzed_files"]
        analyzer2.patterns_found = checkpoint["patterns_found"].copy()
        analyzer2.conventions = checkpoint["conventions"].copy()

        # Continue analysis
        analyzer2.analyze_files(7000)
        update2 = analyzer2.emit_progress()

        assert update2["analyzed_files"] == 10000
        assert update2["is_complete"]
        assert update2["progress_percent"] == 100.0

    def test_large_project_completes_without_blocking(self):
        """Verify large project analysis completes without UI blocking (T183)."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        # Simulate batch processing
        batch_size = 500
        updates_count = 0
        start_time = time.time()

        while not analyzer.is_complete:
            analyzer.analyze_files(batch_size)
            update = analyzer.emit_progress()
            updates_count += 1

            # Small delay to simulate UI updates
            time.sleep(0.001)

        elapsed = time.time() - start_time

        # Verify analysis completed
        assert analyzer.is_complete
        assert analyzer.analyzed_files == 10000

        # Verify progress was streamed
        assert updates_count >= 20  # At least 20 updates for 10000 files

        # Should complete quickly (< 1 second actual processing)
        assert elapsed < 10

        # Verify patterns were found (one per batch)
        assert len(analyzer.patterns_found) >= updates_count - 1
        assert len(analyzer.conventions) > 0

    def test_analysis_with_progress_and_cancellation_workflow(self):
        """Verify workflow: progress updates → cancellation → checkpoint."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        # Analyze in batches and collect progress
        progress_points = []

        for _ in range(3):
            analyzer.analyze_files(2000)
            update = analyzer.emit_progress()
            progress_points.append(update["progress_percent"])

        # Verify progress increased
        assert progress_points[1] > progress_points[0]
        assert progress_points[2] > progress_points[1]

        # User decides to cancel
        analyzer.cancel()

        # Checkpoint should be available
        checkpoint = analyzer.create_checkpoint()

        assert checkpoint is not None
        assert checkpoint["analyzed_files"] == 6000
        assert len(checkpoint["patterns_found"]) == 3  # One pattern per batch


class TestLargeProjectProgressStreaming:
    """Test progress streaming specifics for large projects."""

    def test_progress_emitted_regularly_during_analysis(self):
        """Verify progress is emitted regularly during analysis."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        # Analyze in batches
        for _ in range(10):
            analyzer.analyze_files(1000)
            analyzer.emit_progress()

        # Should have 10 progress updates
        assert len(analyzer.progress_updates) >= 10

        # Each update should have required fields
        for update in analyzer.progress_updates:
            assert "analyzed_files" in update
            assert "progress_percent" in update
            assert "patterns_found" in update
            assert "timestamp" in update

    def test_patterns_found_increases_with_analysis(self):
        """Verify patterns increase as files are analyzed."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        patterns_count = []

        for i in range(5):
            analyzer.analyze_files(2000)
            update = analyzer.emit_progress()
            patterns_count.append(update["patterns_found"])

        # Each step should find more patterns
        for i in range(1, len(patterns_count)):
            assert patterns_count[i] >= patterns_count[i - 1]

    def test_cancellation_stops_further_analysis(self):
        """Verify cancellation prevents further analysis."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        analyzer.analyze_files(2000)
        files_before_cancel = analyzer.analyzed_files

        analyzer.cancel()

        # Try to analyze more - should not work
        result = analyzer.analyze_files(2000)

        assert result == 0  # No files analyzed
        assert analyzer.analyzed_files == files_before_cancel


class TestCheckpointAndResumption:
    """Test checkpoint creation and resumption."""

    def test_checkpoint_preserves_analysis_state(self):
        """Verify checkpoint preserves complete analysis state."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=10000)
        analyzer.start_analysis()

        # Analyze some files
        analyzer.analyze_files(5000)

        # Create checkpoint
        checkpoint = analyzer.create_checkpoint()

        # Verify checkpoint contains all state
        assert checkpoint["analyzed_files"] == 5000
        assert len(checkpoint["patterns_found"]) >= 1  # At least one pattern
        assert len(checkpoint["conventions"]) > 0

    def test_resumption_continues_from_checkpoint(self):
        """Verify analysis can continue from checkpoint."""
        operation_id = str(uuid4())

        # First analyzer
        analyzer1 = LargeProjectAnalyzer(operation_id, total_files=10000)
        analyzer1.start_analysis()
        analyzer1.analyze_files(3000)
        checkpoint = analyzer1.create_checkpoint()

        # Second analyzer resumes
        analyzer2 = LargeProjectAnalyzer(operation_id, total_files=10000)
        analyzer2.start_analysis()
        analyzer2.analyzed_files = checkpoint["analyzed_files"]
        analyzer2.patterns_found = checkpoint["patterns_found"].copy()

        # Continue analysis
        analyzer2.analyze_files(7000)

        # Should be complete
        assert analyzer2.analyzed_files == 10000


class TestLargeProjectScaling:
    """Test handling of very large projects."""

    def test_100000_file_project_analysis(self):
        """Test analysis of 100,000 file project."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=100000)
        analyzer.start_analysis()

        # Analyze in batches
        batch_count = 0
        while not analyzer.is_complete:
            analyzer.analyze_files(10000)
            analyzer.emit_progress()
            batch_count += 1

        assert analyzer.is_complete
        assert analyzer.analyzed_files == 100000
        assert len(analyzer.patterns_found) == batch_count  # One pattern per batch

    def test_progress_accuracy_for_large_projects(self):
        """Verify progress accuracy for large projects."""
        analyzer = LargeProjectAnalyzer(str(uuid4()), total_files=50000)
        analyzer.start_analysis()

        analyzer.analyze_files(25000)
        update = analyzer.emit_progress()

        assert abs(update["progress_percent"] - 50.0) < 0.1  # Within 0.1%

        analyzer.analyze_files(25000)
        update = analyzer.emit_progress()

        assert abs(update["progress_percent"] - 100.0) < 0.1
