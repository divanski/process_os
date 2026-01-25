"""
CLI command for displaying real-time progress from ProcessOS analysis.

Implements:
- T-NEW-010: processos progress CLI command
- Real-time progress display via WebSocket connection
- Formatted progress output with phase descriptions
- ETA calculation and display
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    import websockets
except ImportError:
    websockets = None


@dataclass
class ProgressUpdate:
    """Represents a progress update from server."""

    session_id: str
    phase: str
    progress_percent: float
    current_step: str
    step_number: int
    total_steps: int
    estimated_completion_seconds: float
    confidence_scores: dict
    is_final: bool = False
    summary: Optional[dict] = None

    @classmethod
    def from_message(cls, message: dict) -> "ProgressUpdate":
        """Create ProgressUpdate from WebSocket message."""
        return cls(
            session_id=message.get("session_id", ""),
            phase=message.get("phase", ""),
            progress_percent=message.get("progress_percent", 0.0),
            current_step=message.get("current_step", ""),
            step_number=message.get("step_number", 0),
            total_steps=message.get("total_steps", 4),
            estimated_completion_seconds=message.get(
                "estimated_completion_seconds", 0.0
            ),
            confidence_scores=message.get("confidence_scores", {}),
            is_final=message.get("is_final", False),
            summary=message.get("summary"),
        )


class ProgressFormatter:
    """Formats progress updates for terminal display."""

    @staticmethod
    def format_progress_bar(progress: float, width: int = 40) -> str:
        """Format progress bar for display.

        Args:
            progress: Progress percentage (0-100)
            width: Width of progress bar in characters

        Returns:
            Formatted progress bar string
        """
        filled = int((progress / 100.0) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {progress:.1f}%"

    @staticmethod
    def format_phase_name(phase: str) -> str:
        """Format phase name for display.

        Args:
            phase: Phase identifier

        Returns:
            Formatted phase name
        """
        phase_names = {
            "language_detection": "Language Detection",
            "framework_detection": "Framework Detection",
            "pattern_discovery": "Pattern Discovery",
            "convention_learning": "Convention Learning",
            "complete": "Analysis Complete",
        }
        return phase_names.get(phase, phase.replace("_", " ").title())

    @staticmethod
    def format_time_remaining(seconds: float) -> str:
        """Format remaining time in human-readable format.

        Args:
            seconds: Seconds remaining

        Returns:
            Formatted time string
        """
        if seconds <= 0:
            return "Completing..."

        minutes = int(seconds // 60)
        secs = int(seconds % 60)

        if minutes > 0:
            return f"~{minutes}m {secs}s remaining"
        else:
            return f"~{secs}s remaining"

    @staticmethod
    def format_confidence(confidence: float) -> str:
        """Format confidence score with indicator.

        Args:
            confidence: Confidence score (0.0-1.0)

        Returns:
            Formatted confidence string
        """
        if confidence >= 0.9:
            return f"✓ {confidence:.0%} (High)"
        elif confidence >= 0.7:
            return f"~ {confidence:.0%} (Medium)"
        else:
            return f"⚠ {confidence:.0%} (Low)"

    def format_update(self, update: ProgressUpdate) -> str:
        """Format progress update for display.

        Args:
            update: Progress update from server

        Returns:
            Formatted output string
        """
        lines = []

        # Header
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"Phase: {self.format_phase_name(update.phase)}")
        lines.append("=" * 60)

        # Progress bar
        lines.append(self.format_progress_bar(update.progress_percent))

        # Step information
        lines.append(
            f"Step {update.step_number}/{update.total_steps}: {update.current_step}"
        )

        # Confidence score for current phase
        phase_confidence = update.confidence_scores.get(update.phase, 0.0)
        if phase_confidence > 0:
            lines.append(f"Confidence: {self.format_confidence(phase_confidence)}")

        # Estimated time
        lines.append(self.format_time_remaining(update.estimated_completion_seconds))

        lines.append("-" * 60)

        return "\n".join(lines)

    def format_final_summary(self, update: ProgressUpdate) -> str:
        """Format final summary for display.

        Args:
            update: Final progress update with summary

        Returns:
            Formatted summary string
        """
        lines = []

        lines.append("")
        lines.append("=" * 60)
        lines.append("ANALYSIS COMPLETE")
        lines.append("=" * 60)

        if update.summary:
            summary = update.summary

            # Detected language and framework
            language = summary.get("language", "Unknown")
            framework = summary.get("framework", "Unknown")
            lines.append(f"Language:    {language}")
            lines.append(f"Framework:   {framework}")
            lines.append("")

            # Overall confidence
            confidence = summary.get("overall_confidence", 0.0)
            lines.append(f"Confidence:  {self.format_confidence(confidence)}")
            lines.append("")

            # Analysis metrics
            duration = summary.get("total_duration_seconds", 0.0)
            patterns = summary.get("patterns_discovered", 0)
            conventions = summary.get("conventions_learned", 0)

            lines.append(f"Duration:      {duration:.1f}s")
            lines.append(f"Patterns:      {patterns} discovered")
            lines.append(f"Conventions:   {conventions} learned")
            lines.append("")

        lines.append("=" * 60)
        lines.append("")

        return "\n".join(lines)


class ProgressClient:
    """Client for connecting to ProcessOS WebSocket server and displaying progress."""

    def __init__(self, session_id: str, host: str = "localhost", port: int = 59328):
        """Initialize progress client.

        Args:
            session_id: Session ID to monitor
            host: WebSocket server host
            port: WebSocket server port
        """
        self.session_id = session_id
        self.websocket_url = f"ws://{host}:{port}/processos/ws"
        self.formatter = ProgressFormatter()

    async def connect_and_display(self) -> None:
        """Connect to server and display progress updates."""
        if websockets is None:
            raise RuntimeError(
                "websockets library required. Install with: pip install websockets"
            )

        try:
            async with websockets.connect(self.websocket_url) as websocket:
                print(f"[OK] Connected to {self.websocket_url}")
                print(f"[OK] Session ID: {self.session_id}")
                print("")

                # Listen for progress messages
                async for message_data in websocket:
                    try:
                        message = json.loads(message_data)

                        # Check if this is a PROGRESS message
                        if message.get("type") == "PROGRESS":
                            update = ProgressUpdate.from_message(message)

                            # Check if this is final progress
                            if update.is_final:
                                print(self.formatter.format_final_summary(update))
                                print("[OK] Analysis complete")
                                break
                            else:
                                # Display progress update
                                print(self.formatter.format_update(update))

                    except json.JSONDecodeError:
                        print(f"[ERROR] Invalid JSON received: {message_data}")
                    except Exception as e:
                        print(f"[ERROR] Error processing message: {e}")

        except ConnectionRefusedError:
            print(f"[ERROR] Could not connect to {self.websocket_url}")
            print("[ERROR] Is the ProcessOS server running?")
            raise
        except asyncio.CancelledError:
            print("[OK] Progress display cancelled")
        except Exception as e:
            print(f"[ERROR] Connection error: {e}")
            raise


async def show_progress_command(session_id: str, host: str = "localhost", port: int = 59328) -> None:
    """CLI command to show real-time progress from analysis.

    This command connects to the ProcessOS WebSocket server and displays
    real-time progress updates for a specific analysis session.

    Args:
        session_id: Session ID of the analysis to monitor
        host: WebSocket server host (default: localhost)
        port: WebSocket server port (default: 59328)

    Example:
        processos progress --session-id abc123def456
    """
    client = ProgressClient(session_id, host, port)
    await client.connect_and_display()


def show_progress_sync(
    session_id: str, host: str = "localhost", port: int = 59328
) -> None:
    """Synchronous wrapper for show_progress_command.

    Args:
        session_id: Session ID of the analysis to monitor
        host: WebSocket server host
        port: WebSocket server port
    """
    asyncio.run(show_progress_command(session_id, host, port))
