"""
Progress message formatting for human-readable output.

Implements:
- T068: Progress description formatting
- T069: ClaudeCode UI integration point
"""

from typing import Any, Dict, Optional


class ProgressFormatter:
    """
    Formats progress messages for display in user interfaces.

    Converts machine-readable progress data into human-friendly messages.
    """

    @staticmethod
    def format_phase_description(
        phase: str, progress_percent: float, confidence_score: float
    ) -> str:
        """
        Format human-readable phase description.

        Args:
            phase: Analysis phase name
            progress_percent: Progress percentage (0-100)
            confidence_score: Confidence score (0.0-1.0)

        Returns:
            Human-readable description
        """
        phase_names = {
            "language_detection": "Language Detection",
            "framework_detection": "Framework Detection",
            "pattern_discovery": "Pattern Discovery",
            "convention_learning": "Convention Learning",
            "complete": "Analysis Complete",
        }

        phase_name = phase_names.get(phase, phase.replace("_", " ").title())

        # Add confidence indicator
        if confidence_score >= 0.9:
            confidence_indicator = "✓ High Confidence"
        elif confidence_score >= 0.7:
            confidence_indicator = "~ Medium Confidence"
        else:
            confidence_indicator = "⚠ Low Confidence"

        return f"{phase_name} ({progress_percent:.0f}%) {confidence_indicator}"

    @staticmethod
    def format_step_description(
        phase: str, step_number: int, total_steps: int, current_step: str
    ) -> str:
        """
        Format step description with context.

        Args:
            phase: Analysis phase
            step_number: Current step number
            total_steps: Total steps in phase
            current_step: Current step description

        Returns:
            Formatted step description
        """
        step_indicator = f"[{step_number}/{total_steps}]"
        return f"{step_indicator} {current_step}"

    @staticmethod
    def format_progress_bar(progress_percent: float, width: int = 30) -> str:
        """
        Format progress bar for terminal display.

        Args:
            progress_percent: Progress percentage (0-100)
            width: Bar width in characters

        Returns:
            Formatted progress bar
        """
        filled = int((progress_percent / 100.0) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {progress_percent:.1f}%"

    @staticmethod
    def format_confidence_scores(
        confidence_scores: Dict[str, float],
    ) -> str:
        """
        Format confidence scores for display.

        Args:
            confidence_scores: Confidence scores by phase

        Returns:
            Formatted confidence display
        """
        lines = []

        for phase, score in confidence_scores.items():
            # Format phase name
            phase_name = phase.replace("_", " ").title()

            # Format score with indicator
            if score >= 0.9:
                indicator = "✓"
            elif score >= 0.7:
                indicator = "~"
            else:
                indicator = "⚠"

            # Format bar
            bar_width = 20
            filled = int((score / 1.0) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)

            line = f"  {indicator} {phase_name}: {bar} {score:.1%}"
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def format_time_estimate(
        estimated_seconds: float,
    ) -> str:
        """
        Format time estimate in human-readable form.

        Args:
            estimated_seconds: Estimated seconds remaining

        Returns:
            Formatted time estimate
        """
        if estimated_seconds <= 0:
            return "Completing..."

        minutes = int(estimated_seconds // 60)
        seconds = int(estimated_seconds % 60)

        if minutes > 0:
            return f"~{minutes}m {seconds}s remaining"
        else:
            return f"~{seconds}s remaining"

    @staticmethod
    def format_final_summary(
        summary: Dict[str, Any],
    ) -> str:
        """
        Format final analysis summary for display.

        Args:
            summary: Final summary data

        Returns:
            Formatted summary
        """
        lines = [
            "",
            "=" * 50,
            "ANALYSIS COMPLETE",
            "=" * 50,
            "",
        ]

        # Language and framework
        language = summary.get("language", "Unknown")
        framework = summary.get("framework", "Unknown")
        lines.append(f"Language:    {language}")
        lines.append(f"Framework:   {framework}")
        lines.append("")

        # Confidence
        confidence = summary.get("overall_confidence", 0.0)
        confidence_percent = f"{confidence:.1%}"
        lines.append(f"Confidence:  {confidence_percent}")
        lines.append("")

        # Metrics
        duration = summary.get("total_duration_seconds", 0.0)
        patterns = summary.get("patterns_discovered", 0)
        conventions = summary.get("conventions_learned", 0)

        lines.append(f"Duration:    {duration:.1f}s")
        lines.append(f"Patterns:    {patterns} discovered")
        lines.append(f"Conventions: {conventions} learned")
        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    @staticmethod
    def format_warning_message(
        warning_type: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format warning message for display.

        Args:
            warning_type: Type of warning
            context: Optional context data

        Returns:
            Formatted warning message
        """
        context = context or {}

        warnings = {
            "low_confidence": (
                "⚠ Low confidence detection detected. "
                "Results may be inaccurate."
            ),
            "mixed_language": (
                "⚠ Multiple languages detected. "
                "Confidence reduced."
            ),
            "no_framework": (
                "⚠ No framework detected. "
                "This may be a custom or simple project."
            ),
        }

        return warnings.get(warning_type, "⚠ Warning")


class UIProgressStreamAdapter:
    """
    Adapts progress streaming for ClaudeCode UI integration.

    Converts internal progress format to UI-friendly messages.
    """

    @staticmethod
    def to_ui_message(progress_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert internal progress message to UI format.

        Args:
            progress_message: Internal progress message

        Returns:
            UI-friendly progress message
        """
        formatter = ProgressFormatter()

        # Build UI message
        ui_message = {
            "type": "progress_update",
            "session_id": progress_message.get("session_id"),
            "phase": progress_message.get("phase"),
            "progress": progress_message.get("progress_percent", 0.0),
            "status": "analyzing",
            "details": {
                "phase_description": progress_message.get(
                    "phase_description", ""
                ),
                "current_step": progress_message.get("current_step", ""),
                "step_indicator": (
                    f"{progress_message.get('step_number', 0)}/"
                    f"{progress_message.get('total_steps', 4)}"
                ),
                "confidence_scores": progress_message.get(
                    "confidence_scores", {}
                ),
                "estimated_time": formatter.format_time_estimate(
                    progress_message.get("estimated_completion_seconds", 0.0)
                ),
                "progress_bar": formatter.format_progress_bar(
                    progress_message.get("progress_percent", 0.0)
                ),
            },
        }

        # If final message, include summary
        if progress_message.get("is_final"):
            ui_message["status"] = "complete"
            ui_message["summary"] = progress_message.get("summary")

        return ui_message

    @staticmethod
    def to_ui_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert analysis summary to UI format.

        Args:
            summary: Analysis summary

        Returns:
            UI-friendly summary
        """
        formatter = ProgressFormatter()

        return {
            "type": "analysis_complete",
            "results": {
                "language": summary.get("language"),
                "framework": summary.get("framework"),
                "overall_confidence": summary.get("overall_confidence", 0.0),
                "duration_seconds": summary.get("total_duration_seconds", 0.0),
            },
            "discovered": {
                "patterns": summary.get("patterns_discovered", 0),
                "conventions": summary.get("conventions_learned", 0),
            },
            "formatted_summary": formatter.format_final_summary(summary),
        }

    @staticmethod
    def format_for_terminal(message: Dict[str, Any]) -> str:
        """
        Format progress message for terminal display.

        Args:
            message: Progress message

        Returns:
            Terminal-formatted string
        """
        formatter = ProgressFormatter()

        lines = [
            f"Phase: {message.get('phase_description')}",
            formatter.format_progress_bar(
                message.get("progress_percent", 0.0)
            ),
            f"Step: {message.get('current_step')}",
        ]

        # Add confidence if available
        confidence = message.get("confidence_scores", {}).get(
            message.get("phase"), 0.0
        )
        if confidence > 0:
            lines.append(f"Confidence: {confidence:.1%}")

        # Add time estimate
        est_time = formatter.format_time_estimate(
            message.get("estimated_completion_seconds", 0.0)
        )
        if est_time:
            lines.append(est_time)

        return "\n".join(lines)
