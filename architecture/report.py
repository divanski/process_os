"""
Architecture report formatting and output.

Provides text and JSON output formatters for architecture analysis reports.
"""

import json
from datetime import datetime
from typing import Dict, Any

from process_os.architecture.analyzer import ArchitectureReport


class ArchitectureReportFormatter:
    """Base formatter for architecture reports."""

    @staticmethod
    def format_confidence_bar(confidence: float, width: int = 10) -> str:
        """Generate visual confidence bar.

        Args:
            confidence: Confidence value 0.0-1.0
            width: Width of bar in characters

        Returns:
            Visual bar like: ████████░░ (80%)
        """
        filled = int(confidence * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"{bar} ({confidence:.0%})"


class TextReportFormatter(ArchitectureReportFormatter):
    """Format architecture reports as human-readable text."""

    @staticmethod
    def format(report: ArchitectureReport) -> str:
        """Format report as human-readable text.

        Args:
            report: ArchitectureReport to format

        Returns:
            Formatted text report
        """
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("PROJECT ARCHITECTURE ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        # Summary section
        lines.append("SUMMARY")
        lines.append("-" * 80)
        arch = report.architecture
        lines.append(f"Language:      {arch.language.value.upper()}")
        lines.append(f"Framework:     {arch.framework.value if arch.framework else 'None'}")
        lines.append(f"Confidence:    {ArchitectureReportFormatter.format_confidence_bar(arch.confidence)}")
        lines.append(f"Project Type:  {arch.project_type.value}")
        lines.append(f"Analyzed At:   {report.analyzed_at.isoformat()}")
        lines.append("")

        # Detection Details section
        lines.append("DETECTION DETAILS")
        lines.append("-" * 80)
        if arch.detection_signals:
            lines.append(f"Detection Signals: {len(arch.detection_signals)}")
            for i, signal in enumerate(arch.detection_signals, 1):
                signal_type = getattr(signal, "signal_type", "unknown")
                signal_confidence = getattr(signal, "confidence", 0.0)
                lines.append(
                    f"  {i}. {signal_type} (confidence: {signal_confidence:.0%})"
                )
        else:
            lines.append("No detection signals recorded")
        lines.append("")

        # Patterns section
        if report.patterns:
            lines.append("PATTERNS DISCOVERED")
            lines.append("-" * 80)
            for i, pattern in enumerate(report.patterns, 1):
                pattern_name = getattr(pattern, "name", "Unknown")
                pattern_conf = getattr(pattern, "confidence", 0.0)
                lines.append(f"  {i}. {pattern_name} (confidence: {pattern_conf:.0%})")
            lines.append("")

        # Conventions section
        if report.conventions:
            lines.append("CONVENTIONS LEARNED")
            lines.append("-" * 80)
            lines.append(f"Class Naming:      {report.conventions.class_naming.value}")
            lines.append(f"Method Naming:     {report.conventions.method_naming.value}")
            lines.append(f"Variable Naming:   {report.conventions.variable_naming.value}")
            if report.conventions.namespace_pattern:
                lines.append(f"Namespace Pattern: {report.conventions.namespace_pattern}")
            if report.conventions.directory_pattern:
                lines.append(f"Directory Pattern: {report.conventions.directory_pattern}")
            lines.append("")

        # Recommendations section
        if report.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 80)
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        # Warnings section
        if report.warnings:
            lines.append("WARNINGS")
            lines.append("-" * 80)
            for i, warning in enumerate(report.warnings, 1):
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        # Approval status section
        lines.append("APPROVAL STATUS")
        lines.append("-" * 80)
        if report.user_approved:
            lines.append(f"Status: ✓ APPROVED")
            lines.append(f"Approved At: {report.approved_at.isoformat()}")
        else:
            lines.append(f"Status: ⏳ PENDING")
            lines.append("Action: Run with --confirm flag to approve and enable code generation")
        lines.append("")

        # Footer
        lines.append("=" * 80)

        return "\n".join(lines)


class JSONReportFormatter(ArchitectureReportFormatter):
    """Format architecture reports as JSON."""

    @staticmethod
    def format(report: ArchitectureReport) -> str:
        """Format report as JSON.

        Args:
            report: ArchitectureReport to format

        Returns:
            Formatted JSON report
        """
        report_dict = JSONReportFormatter._to_dict(report)
        return json.dumps(report_dict, indent=2)

    @staticmethod
    def _to_dict(report: ArchitectureReport) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization.

        Args:
            report: ArchitectureReport to convert

        Returns:
            Dictionary representation of report
        """
        arch = report.architecture

        return {
            "analyzed_at": report.analyzed_at.isoformat(),
            "summary": {
                "language": arch.language.value,
                "framework": arch.framework.value if arch.framework else None,
                "confidence": arch.confidence,
                "project_type": arch.project_type.value,
            },
            "detection": {
                "signals_count": len(arch.detection_signals),
                "signals": [
                    {
                        "type": getattr(s, "signal_type", "unknown"),
                        "confidence": getattr(s, "confidence", 0.0),
                    }
                    for s in arch.detection_signals
                ],
            },
            "patterns": {
                "discovered_count": len(report.patterns),
                "patterns": [
                    {
                        "name": getattr(p, "name", "Unknown"),
                        "confidence": getattr(p, "confidence", 0.0),
                    }
                    for p in report.patterns
                ],
            },
            "conventions": {
                "class_naming": report.conventions.class_naming.value
                if report.conventions else None,
                "method_naming": report.conventions.method_naming.value
                if report.conventions else None,
                "variable_naming": report.conventions.variable_naming.value
                if report.conventions else None,
                "namespace_pattern": report.conventions.namespace_pattern
                if report.conventions else None,
            },
            "recommendations": report.recommendations,
            "warnings": report.warnings,
            "approval": {
                "user_approved": report.user_approved,
                "approved_at": report.approved_at.isoformat()
                if report.approved_at else None,
            },
        }
