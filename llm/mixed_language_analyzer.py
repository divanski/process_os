"""
Mixed-language project analysis and low-confidence handling.

Implements:
- T214: MixedLanguageAnalyzer for polyglot projects
- T215: Integration point detection
- T216: LowConfidenceHandler for analysis warnings
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class LanguageStats:
    """Language statistics in project."""

    language: str
    file_count: int
    line_count: int
    percentage: float
    confidence: float


@dataclass
class MixedLanguageAnalysis:
    """Analysis results for mixed-language project."""

    primary_language: str
    secondary_languages: List[str]
    languages: List[LanguageStats]
    dominance_ratio: float  # primary / total
    integration_points: List[str]
    is_polyglot: bool


class MixedLanguageAnalyzer:
    """
    Analyzes mixed-language (polyglot) projects.

    Detects:
    - Primary and secondary languages
    - Language dominance ratio
    - Integration points between languages
    - Polyglot classification (multiple significant languages)
    """

    def __init__(self):
        """Initialize mixed-language analyzer."""
        self.language_stats: List[LanguageStats] = []

    def add_language_stats(self, stats: LanguageStats) -> None:
        """
        Add language statistics.

        Args:
            stats: Language statistics
        """
        self.language_stats.append(stats)

    def analyze(self) -> MixedLanguageAnalysis:
        """
        Analyze mixed-language project.

        Returns:
            Mixed-language analysis with language breakdown,
            dominance ratio, and detected integration points
        """
        if not self.language_stats:
            return MixedLanguageAnalysis(
                primary_language="unknown",
                secondary_languages=[],
                languages=[],
                dominance_ratio=0.0,
                integration_points=[],
                is_polyglot=False,
            )

        # Sort by file count (proxy for dominance)
        sorted_stats = sorted(
            self.language_stats, key=lambda x: x.file_count, reverse=True
        )

        primary = sorted_stats[0]
        secondaries = sorted_stats[1:]

        # Calculate dominance ratio
        total_files = sum(s.file_count for s in self.language_stats)
        dominance_ratio = primary.file_count / total_files if total_files > 0 else 0.0

        # Determine if polyglot (multiple significant languages)
        # Threshold: secondary language >10% of total files
        is_polyglot = (
            len(secondaries) > 0
            and secondaries[0].file_count > total_files * 0.1
        )

        return MixedLanguageAnalysis(
            primary_language=primary.language,
            secondary_languages=[s.language for s in secondaries],
            languages=sorted_stats,
            dominance_ratio=dominance_ratio,
            integration_points=self._find_integration_points(sorted_stats),
            is_polyglot=is_polyglot,
        )

    def _find_integration_points(
        self, stats: List[LanguageStats]
    ) -> List[str]:
        """
        Find integration points between languages.

        Detects common polyglot patterns:
        - C++/Python: Native extensions/bindings
        - JavaScript/Python: REST API, microservices
        - Java/JavaScript: Spring Boot + frontend
        - PHP/JavaScript: Web with AJAX

        Args:
            stats: Sorted language stats

        Returns:
            List of integration points
        """
        integration_points = []
        languages = {s.language for s in stats}

        if "Python" in languages and "C++" in languages:
            integration_points.append("C++/Python bindings")

        if "JavaScript" in languages and "Python" in languages:
            integration_points.append("REST API")

        if "Java" in languages and "JavaScript" in languages:
            integration_points.append("Spring Boot + JavaScript frontend")

        if "PHP" in languages and "JavaScript" in languages:
            integration_points.append("AJAX integration")

        if "Go" in languages and "JavaScript" in languages:
            integration_points.append("Go backend + JS frontend")

        if "Rust" in languages and "WebAssembly" in languages:
            integration_points.append("Rust/WebAssembly")

        return integration_points


@dataclass
class ConfidenceAnalysis:
    """Low-confidence analysis warning."""

    overall_confidence: float
    phase_confidences: Dict[str, float]
    low_confidence_phases: List[str]
    recommendations: List[str]
    can_proceed: bool


class LowConfidenceHandler:
    """
    Handles low-confidence analysis results (<0.90).

    Provides:
    - Confidence threshold checking
    - Per-phase confidence reporting
    - Actionable recommendations
    - Proceed/block decision (threshold: 0.70)
    """

    # Confidence thresholds
    SUCCESS_THRESHOLD = 0.90  # Analysis successful without warnings
    PROCEED_THRESHOLD = 0.70  # Minimum to proceed (with warnings)

    def __init__(self, confidence_threshold: float = 0.90):
        """
        Initialize handler.

        Args:
            confidence_threshold: Confidence threshold (default 0.90)
        """
        self.threshold = confidence_threshold

    def analyze_confidence(
        self, phase_scores: Dict[str, float]
    ) -> ConfidenceAnalysis:
        """
        Analyze confidence levels across analysis phases.

        Args:
            phase_scores: Confidence scores per phase
            - language_detection: 0.0-1.0
            - framework_detection: 0.0-1.0
            - pattern_discovery: 0.0-1.0
            - convention_learning: 0.0-1.0

        Returns:
            Confidence analysis with recommendations
        """
        overall = (
            sum(phase_scores.values()) / len(phase_scores)
            if phase_scores
            else 0.0
        )

        low_phases = [
            phase
            for phase, score in phase_scores.items()
            if score < self.threshold
        ]

        recommendations = self._generate_recommendations(
            phase_scores, low_phases
        )

        # Can proceed if overall >= 0.70 (proceed threshold)
        can_proceed = overall >= self.PROCEED_THRESHOLD

        return ConfidenceAnalysis(
            overall_confidence=overall,
            phase_confidences=phase_scores.copy(),
            low_confidence_phases=low_phases,
            recommendations=recommendations,
            can_proceed=can_proceed,
        )

    def _generate_recommendations(
        self, phase_scores: Dict[str, float], low_phases: List[str]
    ) -> List[str]:
        """
        Generate recommendations for low confidence phases.

        Provides specific guidance for each low-confidence phase:
        - Language detection: Manual verification of detected language
        - Framework detection: Check for framework markers
        - Pattern discovery: Review discovered patterns for completeness
        - Convention learning: Verify detected conventions

        Args:
            phase_scores: Phase scores
            low_phases: Phases with low confidence

        Returns:
            List of recommendations
        """
        recommendations = []

        for phase in low_phases:
            score = phase_scores.get(phase, 0.0)

            if phase == "language_detection" and score < 0.70:
                recommendations.append(
                    "Verify language detection manually (detection confidence low)"
                )
            elif phase == "framework_detection" and score < 0.70:
                recommendations.append(
                    "Check framework markers manually (detection inconclusive)"
                )
            elif phase == "pattern_discovery" and score < 0.70:
                recommendations.append(
                    "Review discovered patterns (may be incomplete)"
                )
            elif phase == "convention_learning" and score < 0.70:
                recommendations.append(
                    "Verify conventions (detection may be inaccurate)"
                )

        return recommendations

    def should_block_code_generation(
        self, phase_scores: Dict[str, float]
    ) -> bool:
        """
        Determine if code generation should be blocked.

        Code generation blocked when overall confidence < 0.70
        (below proceed threshold).

        Args:
            phase_scores: Phase confidence scores

        Returns:
            True if code generation should be blocked
        """
        overall = (
            sum(phase_scores.values()) / len(phase_scores)
            if phase_scores
            else 0.0
        )

        return overall < self.PROCEED_THRESHOLD

    def get_confidence_level(
        self, overall_confidence: float
    ) -> str:
        """
        Get human-readable confidence level.

        Args:
            overall_confidence: Overall confidence score (0.0-1.0)

        Returns:
            Confidence level: "High", "Medium", "Low", "Critical"
        """
        if overall_confidence >= 0.90:
            return "High"
        elif overall_confidence >= 0.80:
            return "Medium"
        elif overall_confidence >= 0.70:
            return "Low"
        else:
            return "Critical"
