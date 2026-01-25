"""
Real-time progress streaming during architecture analysis.

Implements:
- T055: ProgressStreamManager class
- T056: Progress signal detection
- T057: Signal confidence scoring
- T058: Progress message construction
- T059: Phase description generation
- T060: Progress percent calculation
- T061: Progress update timing
- T062: Confidence scores calculation
- T063: Estimated completion calculation
- T064: Final progress message construction
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class SignalDetector:
    """
    Detects and scores analysis signals during architecture analysis.

    Signals from:
    - File extensions and naming patterns
    - Import statements and dependencies
    - Framework markers and conventions
    - Convention patterns and style
    """

    def __init__(self):
        """Initialize signal detector."""
        self.detected_signals = {
            "language_detection": [],
            "framework_detection": [],
            "pattern_discovery": [],
            "convention_learning": [],
        }

    def detect_language_signals(
        self, files_analyzed: int, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect language signals from file analysis.

        Signals include:
        - File extensions (.php, .js, .py, etc.)
        - Import/require statements
        - Shebang lines
        - Package managers (composer.json, package.json, etc.)

        Args:
            files_analyzed: Number of files analyzed
            language: Detected language if any

        Returns:
            List of detected signals
        """
        signals = []

        if files_analyzed > 0:
            signals.append(
                {
                    "signal_type": "file_extension_analysis",
                    "strength": min(1.0, files_analyzed / 100.0),
                }
            )

        if language:
            signals.append(
                {
                    "signal_type": "language_identified",
                    "language": language,
                    "strength": 0.95,
                }
            )

        return signals

    def detect_framework_signals(
        self, framework: Optional[str] = None, markers_found: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Detect framework signals.

        Signals include:
        - Framework-specific files (composer.json, package.json, etc.)
        - Directory structures (app/, src/, vendor/, node_modules/, etc.)
        - Characteristic imports

        Args:
            framework: Detected framework name
            markers_found: Number of framework markers detected

        Returns:
            List of detected signals
        """
        signals = []

        if markers_found > 0:
            signals.append(
                {
                    "signal_type": "framework_markers",
                    "markers_count": markers_found,
                    "strength": min(1.0, markers_found / 5.0),
                }
            )

        if framework:
            signals.append(
                {
                    "signal_type": "framework_identified",
                    "framework": framework,
                    "strength": 0.90,
                }
            )

        return signals

    def detect_pattern_signals(
        self, patterns_found: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Detect architectural patterns.

        Signals include:
        - MVC pattern indicators
        - Service layer patterns
        - Repository patterns
        - Factory patterns

        Args:
            patterns_found: Number of patterns detected

        Returns:
            List of detected signals
        """
        signals = []

        if patterns_found > 0:
            signals.append(
                {
                    "signal_type": "patterns_detected",
                    "count": patterns_found,
                    "strength": min(1.0, patterns_found / 5.0),
                }
            )

        return signals

    def detect_convention_signals(
        self, conventions_found: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Detect coding conventions.

        Signals include:
        - Naming conventions (camelCase, snake_case, etc.)
        - Code organization patterns
        - Documentation style
        - Test structure

        Args:
            conventions_found: Number of conventions detected

        Returns:
            List of detected signals
        """
        signals = []

        if conventions_found > 0:
            signals.append(
                {
                    "signal_type": "conventions_detected",
                    "count": conventions_found,
                    "strength": min(1.0, conventions_found / 5.0),
                }
            )

        return signals

    def aggregate_confidence(
        self, signals: List[Dict[str, Any]]
    ) -> float:
        """
        Aggregate confidence score from multiple signals.

        Args:
            signals: List of detected signals

        Returns:
            Aggregated confidence (0.0-1.0)
        """
        if not signals:
            return 0.0

        # Weighted average of signal strengths
        total_strength = sum(s.get("strength", 0.0) for s in signals)
        return min(1.0, total_strength / len(signals))


class RateLimiter:
    """
    Enforces rate limiting for progress messages.

    Rules:
    - Maximum 1 message per second
    - Average 1-2 seconds between messages
    - Allows burst handling
    """

    def __init__(self, max_per_second: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            max_per_second: Maximum messages per second
        """
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second  # seconds
        self.last_emission_time: Optional[float] = None
        self.emission_times: List[float] = []

    def should_emit(self, current_time: float) -> bool:
        """
        Determine if message should be emitted now.

        Args:
            current_time: Current time in seconds

        Returns:
            True if rate limit allows emission
        """
        if self.last_emission_time is None:
            return True

        time_since_last = current_time - self.last_emission_time
        return time_since_last >= self.min_interval

    def record_emission(self, current_time: float) -> None:
        """
        Record that a message was emitted.

        Args:
            current_time: Current time in seconds
        """
        self.last_emission_time = current_time
        self.emission_times.append(current_time)

        # Keep only recent emission times (last 60 seconds)
        cutoff_time = current_time - 60.0
        self.emission_times = [t for t in self.emission_times if t > cutoff_time]

    def get_average_interval(self) -> float:
        """
        Get average interval between recent emissions.

        Returns:
            Average interval in seconds
        """
        if len(self.emission_times) < 2:
            return 0.0

        intervals = [
            self.emission_times[i] - self.emission_times[i - 1]
            for i in range(1, len(self.emission_times))
        ]

        return sum(intervals) / len(intervals)


class ProgressStreamManager:
    """
    Manages real-time progress streaming during architecture analysis.

    Responsibilities:
    - Collect progress signals
    - Calculate confidence scores
    - Construct progress messages
    - Emit updates at correct intervals
    - Handle cancellation and checkpointing
    """

    def __init__(
        self,
        session_id: str,
        operation_id: str,
        description: str = "Architecture Analysis",
    ):
        """
        Initialize progress stream manager.

        Args:
            session_id: WebSocket session ID
            operation_id: Operation ID
            description: Operation description
        """
        self.session_id = session_id
        self.operation_id = operation_id
        self.description = description

        # State tracking
        self.status = "active"  # active, cancelled, completed
        self.current_phase = "language_detection"
        self.progress_percent = 0.0
        self.phase_progress = {
            "language_detection": 0.0,
            "framework_detection": 0.0,
            "pattern_discovery": 0.0,
            "convention_learning": 0.0,
        }

        # Signal and confidence tracking
        self.signal_detector = SignalDetector()
        self.confidence_scores = {
            "language_detection": 0.0,
            "framework_detection": 0.0,
            "pattern_discovery": 0.0,
            "convention_learning": 0.0,
        }

        # Timing
        self.start_time = time.time()
        self.rate_limiter = RateLimiter(max_per_second=1.0)
        self.progress_updates: List[Dict[str, Any]] = []

        # Checkpointing
        self.checkpoints: List[Dict[str, Any]] = []
        self.last_checkpoint: Optional[str] = None

        # Analysis results
        self.analysis_results: Dict[str, Any] = {
            "language": None,
            "framework": None,
            "patterns_discovered": 0,
            "conventions_learned": 0,
        }

    def update_progress(
        self,
        phase: str,
        progress_percent: float,
        current_step: str,
        step_number: int,
        total_steps: int,
        confidence_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Update progress and construct message.

        Args:
            phase: Current analysis phase
            progress_percent: Progress percentage (0-100)
            current_step: Description of current step
            step_number: Current step number
            total_steps: Total steps in phase
            confidence_scores: Optional explicit confidence scores

        Returns:
            Constructed progress message
        """
        current_time = time.time()

        # Check rate limiting
        if not self.rate_limiter.should_emit(current_time):
            return {}  # Rate limited, don't emit

        # Update state
        self.current_phase = phase
        self.progress_percent = min(100.0, max(0.0, progress_percent))
        self.phase_progress[phase] = progress_percent

        # Update confidence scores
        if confidence_scores:
            self.confidence_scores.update(confidence_scores)

        # Construct message
        message = {
            "type": "PROGRESS",
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "phase_description": self._get_phase_description(phase),
            "progress_percent": self.progress_percent,
            "current_step": current_step,
            "step_number": step_number,
            "total_steps": total_steps,
            "estimated_completion_seconds": self._estimate_completion_time(),
            "is_final": False,
            "confidence_scores": self.confidence_scores.copy(),
        }

        # Record rate limiter
        self.rate_limiter.record_emission(current_time)

        # Store update
        self.progress_updates.append(message)

        return message

    def emit_final_summary(
        self,
        language: str,
        framework: str,
        patterns_discovered: int,
        conventions_learned: int,
        overall_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Emit final progress message with analysis summary.

        Args:
            language: Detected language
            framework: Detected framework
            patterns_discovered: Number of patterns found
            conventions_learned: Number of conventions learned
            overall_confidence: Optional explicit overall confidence

        Returns:
            Final progress message
        """
        current_time = time.time()
        elapsed_seconds = current_time - self.start_time

        # Calculate overall confidence
        if overall_confidence is None:
            scores = list(self.confidence_scores.values())
            overall_confidence = (
                sum(scores) / len(scores) if scores else 0.0
            )

        # Store analysis results
        self.analysis_results = {
            "language": language,
            "framework": framework,
            "patterns_discovered": patterns_discovered,
            "conventions_learned": conventions_learned,
            "overall_confidence": overall_confidence,
        }

        # Construct final message
        final_message = {
            "type": "PROGRESS",
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "timestamp": datetime.now().isoformat(),
            "phase": "complete",
            "phase_description": "Analysis Complete",
            "progress_percent": 100.0,
            "current_step": "Analysis complete",
            "step_number": 4,
            "total_steps": 4,
            "estimated_completion_seconds": 0.0,
            "is_final": True,
            "confidence_scores": self.confidence_scores.copy(),
            "summary": {
                "language": language,
                "framework": framework,
                "overall_confidence": overall_confidence,
                "total_duration_seconds": elapsed_seconds,
                "patterns_discovered": patterns_discovered,
                "conventions_learned": conventions_learned,
            },
        }

        # Store update
        self.progress_updates.append(final_message)
        self.status = "completed"

        return final_message

    def cancel_stream(self, reason: str = "") -> None:
        """
        Cancel the progress stream.

        Saves checkpoint before cancellation.

        Args:
            reason: Cancellation reason
        """
        # Save checkpoint
        self.create_checkpoint(reason)

        # Mark as cancelled
        self.status = "cancelled"

    def create_checkpoint(self, reason: str = "") -> str:
        """
        Create checkpoint of current progress state.

        Args:
            reason: Reason for checkpoint (e.g., "user_cancelled")

        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid4())
        current_time = time.time()

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "operation_id": self.operation_id,
            "timestamp": datetime.now().isoformat(),
            "phase": self.current_phase,
            "progress_percent": self.progress_percent,
            "reason": reason,
            "state_data": {
                "phase_progress": self.phase_progress.copy(),
                "confidence_scores": self.confidence_scores.copy(),
                "updates_emitted": len(self.progress_updates),
                "elapsed_seconds": current_time - self.start_time,
            },
        }

        self.checkpoints.append(checkpoint)
        self.last_checkpoint = checkpoint_id

        return checkpoint_id

    def resume_from_checkpoint(
        self, checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resume progress from checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to resume from

        Returns:
            Checkpoint data or None if not found
        """
        # Find checkpoint
        for checkpoint in self.checkpoints:
            if checkpoint["checkpoint_id"] == checkpoint_id:
                # Restore state
                self.current_phase = checkpoint["phase"]
                self.progress_percent = checkpoint["progress_percent"]
                self.phase_progress = checkpoint["state_data"][
                    "phase_progress"
                ].copy()
                self.confidence_scores = checkpoint["state_data"][
                    "confidence_scores"
                ].copy()

                # Resume streaming
                self.status = "active"

                return checkpoint

        return None

    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get current progress summary.

        Returns:
            Progress summary
        """
        current_time = time.time()
        elapsed_seconds = current_time - self.start_time

        return {
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "status": self.status,
            "current_phase": self.current_phase,
            "progress_percent": self.progress_percent,
            "elapsed_seconds": elapsed_seconds,
            "confidence_scores": self.confidence_scores.copy(),
            "updates_emitted": len(self.progress_updates),
            "checkpoints_created": len(self.checkpoints),
            "analysis_results": self.analysis_results.copy(),
        }

    def _get_phase_description(self, phase: str) -> str:
        """
        Get human-readable description of analysis phase.

        Args:
            phase: Phase name

        Returns:
            Human-readable description
        """
        descriptions = {
            "language_detection": "Detecting project programming language",
            "framework_detection": "Identifying framework and dependencies",
            "pattern_discovery": "Discovering architectural patterns",
            "convention_learning": "Learning code conventions",
            "complete": "Analysis Complete",
        }

        return descriptions.get(phase, f"Analyzing {phase}")

    def _estimate_completion_time(self) -> float:
        """
        Estimate remaining completion time.

        Uses running average of progress rate.

        Returns:
            Estimated seconds remaining
        """
        if self.progress_percent <= 0:
            return 0.0

        current_time = time.time()
        elapsed = current_time - self.start_time

        # Estimate total time based on progress rate
        if self.progress_percent > 0:
            estimated_total = (elapsed / self.progress_percent) * 100.0
            remaining = estimated_total - elapsed
            return max(0.0, remaining)

        return 0.0

    def get_all_updates(self) -> List[Dict[str, Any]]:
        """
        Get all progress updates emitted so far.

        Returns:
            List of progress messages
        """
        return self.progress_updates.copy()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ProgressStreamManager(session={self.session_id}, "
            f"progress={self.progress_percent:.1f}%, "
            f"status={self.status})"
        )
