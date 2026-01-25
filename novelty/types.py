"""
Novel Task Detection Data Model - Type Definitions

Domain entities for novelty detection and custom problem-solving strategies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class ScoringBreakdown:
    """
    Detailed breakdown of novelty similarity scoring.

    Hybrid algorithm: 60% semantic + 40% structural
    """

    semantic_score: float  # [0.0, 1.0] - 60% weight
    structural_score: float  # [0.0, 1.0] - 40% weight
    overall_similarity: float  # [0.0, 1.0] - weighted average

    # Component details
    semantic_details: Dict[str, Any] = field(default_factory=dict)
    structural_details: Dict[str, Any] = field(default_factory=dict)

    # Similar patterns found
    similar_patterns: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "semantic_score": self.semantic_score,
            "structural_score": self.structural_score,
            "overall_similarity": self.overall_similarity,
            "semantic_details": self.semantic_details,
            "structural_details": self.structural_details,
            "similar_patterns": self.similar_patterns,
        }


@dataclass
class NovelTaskIndicator:
    """
    Indicator that a task is novel (not covered by existing patterns).

    Novel tasks are those with <85% similarity to known patterns.
    When detected, ProcessOS generates custom problem-solving strategies
    instead of applying existing patterns.
    """

    task_id: UUID
    session_id: UUID
    timestamp: datetime

    # Task information
    task_description: str
    detected_language: str
    detected_framework: str

    # Novelty determination
    is_novel: bool  # similarity_score < 0.85
    similarity_score: float  # [0.0, 1.0]
    novelty_threshold: float = 0.85

    # Scoring breakdown
    scoring_breakdown: Optional[ScoringBreakdown] = None

    # Novel task explanation
    novelty_explanation: str = ""

    # Custom problem-solving strategy
    custom_problem_solving_strategy: Optional[Dict[str, Any]] = None

    # User override
    user_override: bool = False
    override_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": str(self.task_id),
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "task_description": self.task_description,
            "detected_language": self.detected_language,
            "detected_framework": self.detected_framework,
            "is_novel": self.is_novel,
            "similarity_score": self.similarity_score,
            "novelty_threshold": self.novelty_threshold,
            "scoring_breakdown": self.scoring_breakdown.to_dict()
            if self.scoring_breakdown
            else None,
            "novelty_explanation": self.novelty_explanation,
            "custom_problem_solving_strategy": self.custom_problem_solving_strategy,
            "user_override": self.user_override,
            "override_reason": self.override_reason,
        }
