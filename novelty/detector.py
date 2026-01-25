"""
Novel task detection using hybrid similarity scoring.

Detects when tasks are fundamentally new vs. pattern copies.
Uses 60% semantic + 40% structural scoring with <0.85 threshold for novelty.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import os


@dataclass
class ScoringBreakdown:
    """Breakdown of similarity scoring calculation."""

    semantic_score: float  # 0.0-1.0
    structural_score: float  # 0.0-1.0
    hybrid_score: float  # 0.0-1.0 (60% semantic + 40% structural)
    is_novel: bool  # < 0.85 = novel
    similar_patterns: List[Dict[str, Any]]
    explanation: str


class NoveltyDetector:
    """
    Detects novel tasks using hybrid similarity scoring.

    Uses combination of semantic and structural analysis to determine
    if a task requires custom problem-solving or can use existing patterns.
    """

    NOVELTY_THRESHOLD = 0.85  # Tasks with score < 0.85 are novel
    SEMANTIC_WEIGHT = 0.60
    STRUCTURAL_WEIGHT = 0.40
    SEMANTIC_SIMILARITY_THRESHOLD = 0.85  # 85%+ similarity to patterns

    def __init__(self, patterns_dir: Optional[str] = None):
        """
        Initialize NoveltyDetector.

        Args:
            patterns_dir: Optional directory for storing pattern data
        """
        self.known_patterns = {}
        self.detection_cache = {}
        self.patterns_dir = patterns_dir

        if patterns_dir and os.path.exists(patterns_dir):
            self._load_patterns()

    def add_pattern(
        self,
        pattern_name: str,
        description: str,
        structure: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add a known pattern for comparison.

        Args:
            pattern_name: Name of the pattern
            description: Text description of the pattern
            structure: Code structure representation
            metadata: Optional metadata about the pattern
        """
        self.known_patterns[pattern_name] = {
            "name": pattern_name,
            "description": description,
            "structure": structure,
            "metadata": metadata or {},
        }

    def detect_novelty(
        self,
        task_description: str,
        task_structure: str,
    ) -> ScoringBreakdown:
        """
        Detect if task is novel using hybrid similarity scoring.

        Returns ScoringBreakdown with:
        - semantic_score: 60% weight (description similarity)
        - structural_score: 40% weight (code structure similarity)
        - hybrid_score: weighted combination
        - is_novel: True if score < 0.85
        - similar_patterns: Patterns with high scores
        - explanation: Why task is novel or not
        """
        # Calculate component scores
        semantic_score = self._calculate_semantic_similarity(task_description)
        structural_score = self._calculate_structural_similarity(task_structure)

        # Calculate hybrid score
        hybrid_score = (
            semantic_score * self.SEMANTIC_WEIGHT +
            structural_score * self.STRUCTURAL_WEIGHT
        )

        # Determine novelty
        is_novel = hybrid_score < self.NOVELTY_THRESHOLD

        # Find similar patterns
        similar_patterns = self._find_similar_patterns(semantic_score, structural_score)

        # Generate explanation
        explanation = self._generate_explanation(hybrid_score, is_novel, similar_patterns)

        return ScoringBreakdown(
            semantic_score=semantic_score,
            structural_score=structural_score,
            hybrid_score=hybrid_score,
            is_novel=is_novel,
            similar_patterns=similar_patterns,
            explanation=explanation,
        )

    def _calculate_semantic_similarity(self, task_description: str) -> float:
        """
        Calculate semantic similarity (60% weight).

        Compares task description with pattern descriptions.
        Returns 0.0-1.0 where 1.0 = perfect match.
        """
        if not self.known_patterns:
            return 0.5  # Default if no patterns

        # Find maximum similarity with any pattern
        max_similarity = 0.0

        for pattern_name, pattern in self.known_patterns.items():
            pattern_desc = pattern["description"].lower()
            task_desc = task_description.lower()

            # Word overlap similarity (Jaccard)
            task_words = set(task_desc.split())
            pattern_words = set(pattern_desc.split())

            if task_words and pattern_words:
                overlap = len(task_words & pattern_words)
                union = len(task_words | pattern_words)
                similarity = overlap / union if union > 0 else 0.0
                max_similarity = max(max_similarity, similarity)

        return max_similarity

    def _calculate_structural_similarity(self, task_structure: str) -> float:
        """
        Calculate structural similarity (40% weight).

        Analyzes code structure patterns and file organization.
        Returns 0.0-1.0 where 1.0 = perfect match.
        """
        if not self.known_patterns:
            return 0.5  # Default if no patterns

        # Find maximum similarity with any pattern
        max_similarity = 0.0

        for pattern_name, pattern in self.known_patterns.items():
            pattern_struct = pattern["structure"].lower()
            task_struct = task_structure.lower()

            # Count matching structural elements
            struct_keywords = {"class", "def", "function", "module", "controller", "model", "interface", "service"}
            task_matches = sum(1 for kw in struct_keywords if kw in task_struct)
            pattern_matches = sum(1 for kw in struct_keywords if kw in pattern_struct)

            if task_matches > 0 and pattern_matches > 0:
                similarity = min(task_matches, pattern_matches) / max(task_matches, pattern_matches)
                max_similarity = max(max_similarity, similarity)

        return max_similarity

    def _find_similar_patterns(
        self,
        semantic_score: float,
        structural_score: float,
    ) -> List[Dict[str, Any]]:
        """
        Find patterns with scores above semantic similarity threshold.

        Returns list of similar patterns with scores.
        """
        similar = []

        for pattern_name, pattern in self.known_patterns.items():
            # Include patterns with reasonable semantic similarity
            if semantic_score >= self.SEMANTIC_SIMILARITY_THRESHOLD * 0.8:
                combined = (
                    semantic_score * self.SEMANTIC_WEIGHT +
                    structural_score * self.STRUCTURAL_WEIGHT
                )
                similar.append({
                    "pattern_name": pattern_name,
                    "semantic_score": semantic_score,
                    "structural_score": structural_score,
                    "combined_score": combined,
                    "metadata": pattern.get("metadata", {}),
                })

        return sorted(similar, key=lambda x: x["combined_score"], reverse=True)

    def _generate_explanation(
        self,
        hybrid_score: float,
        is_novel: bool,
        similar_patterns: List[Dict[str, Any]],
    ) -> str:
        """Generate human-readable explanation for novelty determination."""
        if is_novel:
            return (
                f"Task is novel (similarity score: {hybrid_score:.1%}). "
                f"No existing patterns match sufficiently (<85% threshold). "
                f"Custom problem-solving strategy recommended."
            )
        else:
            if similar_patterns:
                top_pattern = similar_patterns[0]
                return (
                    f"Task is not novel (similarity score: {hybrid_score:.1%}). "
                    f"Similar to pattern: {top_pattern['pattern_name']} "
                    f"(match: {top_pattern['combined_score']:.1%}). "
                    f"Standard pattern can be applied."
                )
            return f"Task is not novel (similarity score: {hybrid_score:.1%})"

    def save_scoring_breakdown(
        self,
        task_id: str,
        breakdown: ScoringBreakdown,
        output_dir: str,
    ) -> str:
        """
        Save scoring breakdown to file.

        Args:
            task_id: Unique task identifier
            breakdown: ScoringBreakdown to save
            output_dir: Directory to save breakdown file

        Returns:
            Path to saved file
        """
        os.makedirs(output_dir, exist_ok=True)

        filename = os.path.join(output_dir, f"{task_id}_novelty.json")

        data = {
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "semantic_score": breakdown.semantic_score,
            "structural_score": breakdown.structural_score,
            "hybrid_score": breakdown.hybrid_score,
            "is_novel": breakdown.is_novel,
            "similar_patterns": breakdown.similar_patterns,
            "explanation": breakdown.explanation,
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        return filename

    def _load_patterns(self):
        """Load patterns from directory."""
        pattern_files = [
            f for f in os.listdir(self.patterns_dir)
            if f.endswith(".json")
        ]

        for filename in pattern_files:
            filepath = os.path.join(self.patterns_dir, filename)
            try:
                with open(filepath, "r") as f:
                    pattern_data = json.load(f)
                    self.add_pattern(
                        pattern_data["name"],
                        pattern_data["description"],
                        pattern_data["structure"],
                        pattern_data.get("metadata", {}),
                    )
            except (json.JSONDecodeError, KeyError):
                # Skip malformed files
                continue
