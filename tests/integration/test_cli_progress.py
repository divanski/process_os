"""
Integration tests for CLI progress command.

Tests:
- T-NEW-010: processos progress CLI command
- Progress formatting and display
- WebSocket connection handling
"""

import json
from typing import Dict, Any, List

import pytest

from process_os.cli.progress import (
    ProgressUpdate,
    ProgressFormatter,
    ProgressClient,
)


class TestProgressUpdate:
    """Test ProgressUpdate data class."""

    def test_progress_update_creation(self):
        """Verify ProgressUpdate can be created."""
        update = ProgressUpdate(
            session_id="session123",
            phase="language_detection",
            progress_percent=25.0,
            current_step="Detecting PHP",
            step_number=1,
            total_steps=4,
            estimated_completion_seconds=45.0,
            confidence_scores={"language_detection": 0.95},
        )

        assert update.session_id == "session123"
        assert update.phase == "language_detection"
        assert update.progress_percent == 25.0
        assert update.is_final is False

    def test_progress_update_from_message(self):
        """Verify ProgressUpdate can be created from WebSocket message."""
        message = {
            "type": "PROGRESS",
            "session_id": "abc123",
            "phase": "language_detection",
            "progress_percent": 25.0,
            "current_step": "Detecting language",
            "step_number": 1,
            "total_steps": 4,
            "estimated_completion_seconds": 45.0,
            "confidence_scores": {"language_detection": 0.85},
            "is_final": False,
        }

        update = ProgressUpdate.from_message(message)

        assert update.session_id == "abc123"
        assert update.phase == "language_detection"
        assert update.progress_percent == 25.0
        assert update.confidence_scores["language_detection"] == 0.85

    def test_final_progress_update(self):
        """Verify final progress update with summary."""
        message = {
            "type": "PROGRESS",
            "session_id": "session123",
            "phase": "complete",
            "progress_percent": 100.0,
            "current_step": "Analysis complete",
            "step_number": 4,
            "total_steps": 4,
            "estimated_completion_seconds": 0.0,
            "confidence_scores": {"convention_learning": 0.8},
            "is_final": True,
            "summary": {
                "language": "PHP",
                "framework": "Laravel",
                "overall_confidence": 0.92,
                "total_duration_seconds": 45.2,
                "patterns_discovered": 5,
                "conventions_learned": 8,
            },
        }

        update = ProgressUpdate.from_message(message)

        assert update.is_final is True
        assert update.summary is not None
        assert update.summary["language"] == "PHP"


class TestProgressFormatter:
    """Test ProgressFormatter for terminal display."""

    def test_format_progress_bar(self):
        """Verify progress bar formatting."""
        formatter = ProgressFormatter()

        bar = formatter.format_progress_bar(50.0)
        assert "[" in bar and "]" in bar
        assert "50.0%" in bar
        assert "█" in bar
        assert "░" in bar

    def test_format_progress_bar_empty(self):
        """Verify empty progress bar."""
        formatter = ProgressFormatter()
        bar = formatter.format_progress_bar(0.0)
        assert "0.0%" in bar
        assert "░" in bar

    def test_format_progress_bar_full(self):
        """Verify full progress bar."""
        formatter = ProgressFormatter()
        bar = formatter.format_progress_bar(100.0)
        assert "100.0%" in bar
        assert "█" in bar

    def test_format_phase_name(self):
        """Verify phase name formatting."""
        formatter = ProgressFormatter()

        assert formatter.format_phase_name("language_detection") == "Language Detection"
        assert formatter.format_phase_name("framework_detection") == "Framework Detection"
        assert formatter.format_phase_name("pattern_discovery") == "Pattern Discovery"
        assert formatter.format_phase_name("convention_learning") == "Convention Learning"
        assert formatter.format_phase_name("complete") == "Analysis Complete"

    def test_format_time_remaining(self):
        """Verify time remaining formatting."""
        formatter = ProgressFormatter()

        # Seconds only
        assert "30s" in formatter.format_time_remaining(30)

        # Minutes and seconds
        time_str = formatter.format_time_remaining(125)
        assert "2m" in time_str
        assert "5s" in time_str

        # Zero time
        assert "Completing" in formatter.format_time_remaining(0)

    def test_format_confidence_high(self):
        """Verify confidence formatting for high confidence."""
        formatter = ProgressFormatter()
        conf = formatter.format_confidence(0.95)
        assert "✓" in conf
        assert "95%" in conf
        assert "High" in conf

    def test_format_confidence_medium(self):
        """Verify confidence formatting for medium confidence."""
        formatter = ProgressFormatter()
        conf = formatter.format_confidence(0.8)
        assert "~" in conf
        assert "80%" in conf
        assert "Medium" in conf

    def test_format_confidence_low(self):
        """Verify confidence formatting for low confidence."""
        formatter = ProgressFormatter()
        conf = formatter.format_confidence(0.6)
        assert "⚠" in conf
        assert "60%" in conf
        assert "Low" in conf

    def test_format_update(self):
        """Verify progress update formatting."""
        formatter = ProgressFormatter()
        update = ProgressUpdate(
            session_id="session123",
            phase="language_detection",
            progress_percent=25.0,
            current_step="Detecting language",
            step_number=1,
            total_steps=4,
            estimated_completion_seconds=45.0,
            confidence_scores={"language_detection": 0.95},
        )

        formatted = formatter.format_update(update)

        assert "Language Detection" in formatted
        assert "25.0%" in formatted
        assert "[" in formatted and "]" in formatted
        assert "Step 1/4" in formatted
        assert "Detecting language" in formatted

    def test_format_final_summary(self):
        """Verify final summary formatting."""
        formatter = ProgressFormatter()
        update = ProgressUpdate(
            session_id="session123",
            phase="complete",
            progress_percent=100.0,
            current_step="Analysis complete",
            step_number=4,
            total_steps=4,
            estimated_completion_seconds=0.0,
            confidence_scores={"convention_learning": 0.8},
            is_final=True,
            summary={
                "language": "PHP",
                "framework": "Laravel",
                "overall_confidence": 0.92,
                "total_duration_seconds": 45.2,
                "patterns_discovered": 5,
                "conventions_learned": 8,
            },
        )

        formatted = formatter.format_final_summary(update)

        assert "ANALYSIS COMPLETE" in formatted
        assert "PHP" in formatted
        assert "Laravel" in formatted
        assert "92%" in formatted
        assert "45.2s" in formatted
        assert "5 discovered" in formatted
        assert "8 learned" in formatted


class TestProgressClient:
    """Test ProgressClient for WebSocket communication."""

    def test_progress_client_creation(self):
        """Verify ProgressClient can be created."""
        client = ProgressClient("session123")
        assert client.session_id == "session123"
        assert "ws://localhost:59328" in client.websocket_url

    def test_progress_client_custom_host(self):
        """Verify ProgressClient with custom host/port."""
        client = ProgressClient("session123", host="example.com", port=8080)
        assert "ws://example.com:8080" in client.websocket_url

    def test_progress_client_has_formatter(self):
        """Verify ProgressClient has formatter."""
        client = ProgressClient("session123")
        assert isinstance(client.formatter, ProgressFormatter)


class TestProgressFormatting:
    """Test complete progress formatting workflow."""

    def test_format_all_progress_phases(self):
        """Verify formatting of all 4 progress phases."""
        formatter = ProgressFormatter()

        phases = [
            ("language_detection", 25.0),
            ("framework_detection", 50.0),
            ("pattern_discovery", 75.0),
            ("convention_learning", 100.0),
        ]

        for phase, progress in phases:
            update = ProgressUpdate(
                session_id="session123",
                phase=phase,
                progress_percent=progress,
                current_step=f"Phase: {phase}",
                step_number=int(progress / 25),
                total_steps=4,
                estimated_completion_seconds=max(0, 100 - progress),
                confidence_scores={phase: 0.85},
            )

            formatted = formatter.format_update(update)

            # Verify essential content
            assert formatter.format_phase_name(phase) in formatted
            assert f"{progress:.1f}%" in formatted
            assert "Step" in formatted

    def test_format_with_different_confidence_levels(self):
        """Verify formatting with different confidence levels."""
        formatter = ProgressFormatter()

        confidence_levels = [0.5, 0.7, 0.85, 0.95]

        for confidence in confidence_levels:
            update = ProgressUpdate(
                session_id="session123",
                phase="language_detection",
                progress_percent=25.0,
                current_step="Testing",
                step_number=1,
                total_steps=4,
                estimated_completion_seconds=45.0,
                confidence_scores={"language_detection": confidence},
            )

            formatted = formatter.format_update(update)
            confidence_str = formatter.format_confidence(confidence)

            assert "%" in confidence_str
            assert confidence_str in formatted or confidence_str.split()[0] in formatted

    def test_format_progress_sequence(self):
        """Verify formatting of complete progress sequence."""
        formatter = ProgressFormatter()

        # Simulate complete analysis sequence
        updates = [
            ProgressUpdate(
                session_id="session123",
                phase="language_detection",
                progress_percent=25.0,
                current_step="Detected PHP",
                step_number=1,
                total_steps=4,
                estimated_completion_seconds=45.0,
                confidence_scores={"language_detection": 0.95},
            ),
            ProgressUpdate(
                session_id="session123",
                phase="framework_detection",
                progress_percent=50.0,
                current_step="Detected Laravel",
                step_number=2,
                total_steps=4,
                estimated_completion_seconds=30.0,
                confidence_scores={"framework_detection": 0.9},
            ),
            ProgressUpdate(
                session_id="session123",
                phase="pattern_discovery",
                progress_percent=75.0,
                current_step="Found 5 patterns",
                step_number=3,
                total_steps=4,
                estimated_completion_seconds=15.0,
                confidence_scores={"pattern_discovery": 0.85},
            ),
            ProgressUpdate(
                session_id="session123",
                phase="complete",
                progress_percent=100.0,
                current_step="Analysis complete",
                step_number=4,
                total_steps=4,
                estimated_completion_seconds=0.0,
                confidence_scores={"convention_learning": 0.8},
                is_final=True,
                summary={
                    "language": "PHP",
                    "framework": "Laravel",
                    "overall_confidence": 0.90,
                    "total_duration_seconds": 45.0,
                    "patterns_discovered": 5,
                    "conventions_learned": 8,
                },
            ),
        ]

        # Format each update
        formatted_outputs = []
        for update in updates:
            if update.is_final:
                formatted = formatter.format_final_summary(update)
            else:
                formatted = formatter.format_update(update)
            formatted_outputs.append(formatted)

        # Verify all outputs generated
        assert len(formatted_outputs) == 4

        # Verify first output (language detection)
        assert "Language Detection" in formatted_outputs[0]
        assert "25.0%" in formatted_outputs[0]

        # Verify last output (final summary)
        assert "ANALYSIS COMPLETE" in formatted_outputs[3]
        assert "PHP" in formatted_outputs[3]
        assert "Laravel" in formatted_outputs[3]
