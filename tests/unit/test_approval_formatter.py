"""
Unit tests for approval workflow formatting.

Tests for Phase 5 (US3): User Approval Workflow Formatting

Tests:
- T132-T139: ReviewSummary formatting and UI integration
"""

from typing import Any, Dict, List, Optional

import pytest


class ReviewSummaryFormatter:
    """Formats ReviewSummary for modal display."""

    @staticmethod
    def format_patterns_to_use(patterns: List[Dict[str, Any]]) -> str:
        """
        Format patterns for display (T134).

        Args:
            patterns: List of patterns with confidence and description

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
        Format conventions for display (T135).

        Args:
            conventions: Dict of conventions (naming, namespace, directory, etc.)

        Returns:
            Formatted conventions string
        """
        lines = []

        convention_names = {
            "naming": "Naming Convention",
            "namespace": "Namespace",
            "directory": "Directory Pattern",
            "directory_pattern": "Directory Pattern",
            "psr": "Code Standard",
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
        Format and truncate code preview (T137).

        Args:
            code: Full code to preview
            max_length: Maximum length of preview

        Returns:
            Formatted and truncated code preview
        """
        if len(code) <= max_length:
            return code

        preview = code[:max_length]
        # Find last newline to avoid cutting mid-line
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
        Format complete review summary.

        Args:
            detected_language: Detected language
            detected_framework: Detected framework
            overall_confidence: Overall confidence score
            patterns: Patterns to use
            conventions: Conventions to apply
            issues: Potential issues
            code_preview: Code preview

        Returns:
            Formatted review summary
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("CODE GENERATION REVIEW")
        lines.append("=" * 60)
        lines.append("")

        # Detection
        lines.append("DETECTED TECHNOLOGY:")
        lines.append(f"  Language:   {detected_language}")
        lines.append(f"  Framework:  {detected_framework}")
        lines.append(f"  Confidence: {overall_confidence:.0%}")
        lines.append("")

        # Patterns
        lines.append("PATTERNS TO APPLY:")
        lines.append(ReviewSummaryFormatter.format_patterns_to_use(patterns))
        lines.append("")

        # Conventions
        lines.append("CONVENTIONS TO FOLLOW:")
        lines.append(ReviewSummaryFormatter.format_conventions_to_apply(conventions))
        lines.append("")

        # Issues
        lines.append("POTENTIAL ISSUES:")
        lines.append(ReviewSummaryFormatter.format_potential_issues(issues))
        lines.append("")

        # Code preview
        lines.append("GENERATED CODE PREVIEW:")
        lines.append("-" * 60)
        lines.append(ReviewSummaryFormatter.format_code_preview(code_preview))
        lines.append("-" * 60)

        return "\n".join(lines)


class TestReviewSummaryFormatting:
    """Test ReviewSummary formatting for modal display."""

    def test_format_patterns_with_all_fields(self):
        """Verify formatting of patterns with all fields (T134)."""
        patterns = [
            {
                "name": "MVC",
                "confidence": 0.95,
                "description": "Model View Controller pattern",
                "estimated_lines": 150,
            },
            {
                "name": "Service Container",
                "confidence": 0.90,
                "description": "Dependency injection container",
                "estimated_lines": 100,
            },
        ]

        formatted = ReviewSummaryFormatter.format_patterns_to_use(patterns)

        assert "MVC" in formatted
        assert "95%" in formatted
        assert "Model View Controller" in formatted
        assert "150" in formatted
        assert "Service Container" in formatted
        assert "90%" in formatted

    def test_format_conventions_to_apply(self):
        """Verify formatting of conventions (T135)."""
        conventions = {
            "naming": "camelCase",
            "namespace": "App\\Models",
            "directory_pattern": "app/Models",
            "psr": "PSR-12",
        }

        formatted = ReviewSummaryFormatter.format_conventions_to_apply(conventions)

        assert "camelCase" in formatted
        assert "App\\Models" in formatted
        assert "app/Models" in formatted
        assert "PSR-12" in formatted
        assert "Naming Convention" in formatted or "naming" in formatted

    def test_format_potential_issues(self):
        """Verify formatting of potential issues (T136)."""
        issues = [
            "Consider adding request validation",
            "Add error handling for database operations",
            "Implement logging",
        ]

        formatted = ReviewSummaryFormatter.format_potential_issues(issues)

        assert "⚠" in formatted
        assert "validation" in formatted
        assert "error handling" in formatted
        assert "logging" in formatted

    def test_format_potential_issues_empty(self):
        """Verify formatting when no issues present."""
        formatted = ReviewSummaryFormatter.format_potential_issues([])
        assert "No known issues" in formatted

    def test_format_code_preview_truncation(self):
        """Verify code preview truncation to max length (T137)."""
        long_code = "<?php\n" + "// Comment\n" * 100 + "class User {}"

        formatted = ReviewSummaryFormatter.format_code_preview(long_code, max_length=200)

        assert len(formatted) <= 210  # Allow a few extra for newline handling
        assert "truncated" in formatted
        assert long_code.startswith(formatted.split("\n... (truncated)")[0])

    def test_format_code_preview_no_truncation_needed(self):
        """Verify short code preview is not truncated."""
        short_code = "<?php\nclass User {}"

        formatted = ReviewSummaryFormatter.format_code_preview(short_code)

        assert formatted == short_code
        assert "truncated" not in formatted

    def test_format_code_preview_first_500_characters(self):
        """Verify code preview uses 500 character default limit."""
        code = "<?php\n" + "x" * 600

        formatted = ReviewSummaryFormatter.format_code_preview(code)

        # Should be truncated
        assert "truncated" in formatted
        # Should not exceed 500 + some buffer for formatting
        assert len(formatted.split("\n... (truncated)")[0]) <= 500

    def test_format_complete_review_summary(self):
        """Verify complete review summary formatting (T132-T139)."""
        patterns = [
            {"name": "MVC", "confidence": 0.95, "description": "Pattern", "estimated_lines": 150}
        ]

        conventions = {"naming": "camelCase", "namespace": "App"}

        issues = ["Consider validation"]

        code = "<?php\nclass User {}"

        formatted = ReviewSummaryFormatter.format_review_summary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns=patterns,
            conventions=conventions,
            issues=issues,
            code_preview=code,
        )

        # Verify all sections present
        assert "CODE GENERATION REVIEW" in formatted
        assert "PHP" in formatted
        assert "Laravel" in formatted
        assert "92%" in formatted
        assert "PATTERNS TO APPLY" in formatted
        assert "MVC" in formatted
        assert "CONVENTIONS TO FOLLOW" in formatted
        assert "camelCase" in formatted
        assert "POTENTIAL ISSUES" in formatted
        assert "validation" in formatted
        assert "GENERATED CODE PREVIEW" in formatted
        assert "class User" in formatted


class TestReviewSummaryIntegration:
    """Integration tests for ReviewSummary in approval context."""

    def test_formatter_with_high_confidence_analysis(self):
        """Verify formatting for high confidence analysis."""
        patterns = [
            {"name": "MVC", "confidence": 0.95},
            {"name": "Service Container", "confidence": 0.92},
        ]

        formatted = ReviewSummaryFormatter.format_review_summary(
            detected_language="PHP",
            detected_framework="Laravel",
            overall_confidence=0.92,
            patterns=patterns,
            conventions={"naming": "camelCase"},
            issues=[],
            code_preview="<?php class User {}",
        )

        assert "92%" in formatted
        assert "95%" in formatted
        assert "No known issues" in formatted

    def test_formatter_with_low_confidence_warnings(self):
        """Verify formatting includes warnings for low confidence."""
        patterns = [{"name": "Unknown Pattern", "confidence": 0.65}]

        issues = [
            "Low confidence - manual review recommended",
            "Pattern not fully recognized",
        ]

        formatted = ReviewSummaryFormatter.format_review_summary(
            detected_language="Python",
            detected_framework="Unknown",
            overall_confidence=0.65,
            patterns=patterns,
            conventions={},
            issues=issues,
            code_preview="# Python code",
        )

        assert "65%" in formatted
        assert "⚠" in formatted
        assert "Low confidence" in formatted
