"""
Novel Task Detection Module for ProcessOS CI/CL Client Integration

This module provides:
- Hybrid similarity algorithm (60% semantic + 40% structural)
- Novel task detection (<85% similarity threshold)
- Custom problem-solving strategy generation
- Pattern comparison and scoring
"""

from .types import NovelTaskIndicator, ScoringBreakdown

__all__ = [
    "NovelTaskIndicator",
    "ScoringBreakdown",
]
