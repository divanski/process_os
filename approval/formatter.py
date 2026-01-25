"""
Formatter for approval workflow review summaries.

Implements:
- T132-T139: ReviewSummary formatting for modal display
- Pattern formatting with confidence scores
- Convention formatting
- Code preview truncation
"""

from typing import Any, Dict, List


class ReviewSummaryFormatter:
    """Formats ReviewSummary for modal display."""

    @staticmethod
    def format_patterns_to_use(patterns: List[Dict[str, Any]]) -> str:
        """
        Format patterns for modal display (T134).

        Args:
            patterns: List of patterns with metadata

        Returns:
            Formatted patterns string
        """
        lines = []

        for pattern in patterns:
            name = pattern.get("name", "Unknown")
            confidence = pattern.get("confidence", 0.0)
            description = pattern.get("description", "")
            estimated_lines = pattern.get("estimated_lines", 0)

            lines.append(f"• {name}")
            lines.append(f"  Confidence: {confidence:.0%}")
            if description:
                lines.append(f"  Description: {description}")
            if estimated_lines:
                lines.append(f"  Estimated lines: {estimated_lines}")

        return "\n".join(lines)

    @staticmethod
    def format_conventions_to_apply(conventions: Dict[str, Any]) -> str:
        """
        Format conventions for modal display (T135).

        Args:
            conventions: Dictionary of conventions

        Returns:
            Formatted conventions string
        """
        lines = []

        convention_names = {
            "naming": "Naming Convention",
            "namespace": "Namespace/Package",
            "directory": "Directory Pattern",
            "directory_pattern": "Directory Pattern",
            "psr": "Code Standard (PSR)",
            "spacing": "Indentation/Spacing",
        }

        for key, value in conventions.items():
            display_name = convention_names.get(key, key.replace("_", " ").title())
            lines.append(f"• {display_name}: {value}")

        return "\n".join(lines)

    @staticmethod
    def format_potential_issues(issues: List[str]) -> str:
        """
        Format potential issues for display (T136).

        Args:
            issues: List of potential issues

        Returns:
            Formatted issues string
        """
        if not issues:
            return "No known issues"

        lines = []
        for issue in issues:
            lines.append(f"⚠ {issue}")

        return "\n".join(lines)

    @staticmethod
    def format_code_preview(code: str, max_length: int = 500) -> str:
        """
        Format and truncate code preview for display (T137).

        Args:
            code: Full generated code
            max_length: Maximum length of preview (default 500)

        Returns:
            Formatted and truncated code preview
        """
        if len(code) <= max_length:
            return code

        # Truncate to max_length
        preview = code[:max_length]

        # Try to find last newline to avoid cutting mid-line
        last_newline = preview.rfind("\n")
        if last_newline > 0:
            preview = preview[:last_newline]

        return preview + "\n... (truncated)"

    @staticmethod
    def format_review_summary(
        detected_language: str,
        detected_framework: str,
        overall_confidence: float,
        patterns: List[Dict[str, Any]],
        conventions: Dict[str, Any],
        issues: List[str],
        code_preview: str,
    ) -> str:
        """
        Format complete review summary for modal (T132-T139).

        Args:
            detected_language: Detected programming language
            detected_framework: Detected framework
            overall_confidence: Overall confidence score (0-1)
            patterns: Patterns to apply with metadata
            conventions: Conventions to follow
            issues: Potential issues found
            code_preview: Preview of generated code

        Returns:
            Complete formatted review summary
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("CODE GENERATION REVIEW")
        lines.append("=" * 60)
        lines.append("")

        # Detected Technology
        lines.append("DETECTED TECHNOLOGY:")
        lines.append(f"  Language:   {detected_language}")
        lines.append(f"  Framework:  {detected_framework}")
        lines.append(f"  Confidence: {overall_confidence:.0%}")
        lines.append("")

        # Patterns to Apply
        lines.append("PATTERNS TO APPLY:")
        if patterns:
            lines.append(ReviewSummaryFormatter.format_patterns_to_use(patterns))
        else:
            lines.append("  No patterns identified")
        lines.append("")

        # Conventions to Follow
        lines.append("CONVENTIONS TO FOLLOW:")
        if conventions:
            lines.append(ReviewSummaryFormatter.format_conventions_to_apply(conventions))
        else:
            lines.append("  No conventions identified")
        lines.append("")

        # Potential Issues
        lines.append("POTENTIAL ISSUES:")
        lines.append(ReviewSummaryFormatter.format_potential_issues(issues))
        lines.append("")

        # Code Preview
        lines.append("GENERATED CODE PREVIEW:")
        lines.append("-" * 60)
        lines.append(ReviewSummaryFormatter.format_code_preview(code_preview))
        lines.append("-" * 60)
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_confidence_indicator(confidence: float) -> str:
        """
        Format confidence score with visual indicator.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Formatted confidence with indicator
        """
        if confidence >= 0.90:
            return f"✓ {confidence:.0%} (High)"
        elif confidence >= 0.70:
            return f"~ {confidence:.0%} (Medium)"
        else:
            return f"⚠ {confidence:.0%} (Low)"
