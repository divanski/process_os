"""
Unit tests for mixed-language project support.

Tests for Phase 8: Mixed-language project handling

Tests:
- T189-T195: Mixed-language analysis
- T196-T200: Low-confidence analysis handling
"""

import pytest
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
    """Analyzes mixed-language projects."""

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
            Mixed-language analysis
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
        is_polyglot = (
            len(secondaries) > 0
            and secondaries[0].file_count > total_files * 0.1
        )  # >10% threshold

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

        Args:
            stats: Sorted language stats

        Returns:
            List of integration points
        """
        integration_points = []

        if any(s.language == "Python" for s in stats) and any(
            s.language == "C++" for s in stats
        ):
            integration_points.append("C++/Python bindings")

        if any(s.language == "JavaScript" for s in stats) and any(
            s.language == "Python" for s in stats
        ):
            integration_points.append("REST API")

        if any(s.language == "Java" for s in stats) and any(
            s.language == "JavaScript" for s in stats
        ):
            integration_points.append("Spring Boot + JavaScript frontend")

        if any(s.language == "PHP" for s in stats) and any(
            s.language == "JavaScript" for s in stats
        ):
            integration_points.append("AJAX integration")

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
    """Handles low-confidence analysis (<0.90)."""

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
        Analyze confidence levels.

        Args:
            phase_scores: Confidence scores per phase

        Returns:
            Confidence analysis
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

        # Can proceed if overall >= 0.70 (warning threshold)
        can_proceed = overall >= 0.70

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
        Generate recommendations for low confidence.

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


class TestMixedLanguageDetection:
    """Test mixed-language project detection (T189-T192)."""

    def test_single_dominant_language(self):
        """Verify single language project detected correctly (T189)."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=450,
                line_count=25000,
                percentage=90.0,
                confidence=0.95,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="JavaScript",
                file_count=50,
                line_count=2500,
                percentage=10.0,
                confidence=0.90,
            )
        )

        result = analyzer.analyze()

        assert result.primary_language == "Python"
        assert result.dominance_ratio > 0.85
        assert not result.is_polyglot  # Not truly polyglot

    def test_polyglot_project_detection(self):
        """Verify polyglot projects detected (T190)."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="Java",
                file_count=300,
                line_count=50000,
                percentage=40.0,
                confidence=0.92,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="JavaScript",
                file_count=250,
                line_count=15000,
                percentage=35.0,
                confidence=0.88,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=200,
                line_count=8000,
                percentage=25.0,
                confidence=0.85,
            )
        )

        result = analyzer.analyze()

        assert result.is_polyglot is True
        assert result.primary_language == "Java"
        assert len(result.secondary_languages) == 2
        assert "JavaScript" in result.secondary_languages

    def test_three_language_project(self):
        """Verify 3-language project handled (T191)."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="TypeScript",
                file_count=200,
                line_count=12000,
                percentage=50.0,
                confidence=0.93,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=150,
                line_count=8000,
                percentage=30.0,
                confidence=0.90,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="Dockerfile",
                file_count=50,
                line_count=500,
                percentage=20.0,
                confidence=0.95,
            )
        )

        result = analyzer.analyze()

        assert len(result.languages) == 3
        assert result.primary_language == "TypeScript"

    def test_integration_points_detection(self):
        """Verify integration points detected (T192)."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="JavaScript",
                file_count=200,
                line_count=10000,
                percentage=50.0,
                confidence=0.92,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=200,
                line_count=15000,
                percentage=50.0,
                confidence=0.90,
            )
        )

        result = analyzer.analyze()

        assert len(result.integration_points) > 0
        assert any("REST" in point for point in result.integration_points)


class TestLanguageDetectionAccuracy:
    """Test language detection accuracy."""

    def test_language_confidence_high(self):
        """Verify high confidence languages identified."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=450,
                line_count=50000,
                percentage=90.0,
                confidence=0.98,
            )
        )

        result = analyzer.analyze()

        assert result.languages[0].confidence == 0.98

    def test_language_confidence_varies(self):
        """Verify varying language confidence levels."""
        analyzer = MixedLanguageAnalyzer()

        analyzer.add_language_stats(
            LanguageStats(
                language="Python",
                file_count=300,
                line_count=20000,
                percentage=60.0,
                confidence=0.95,
            )
        )

        analyzer.add_language_stats(
            LanguageStats(
                language="Kotlin",  # Less common, might be lower confidence
                file_count=200,
                line_count=15000,
                percentage=40.0,
                confidence=0.75,
            )
        )

        result = analyzer.analyze()

        assert result.languages[0].confidence > result.languages[1].confidence


class TestLowConfidenceHandling:
    """Test low-confidence analysis handling (T196-T200)."""

    def test_low_confidence_detection_below_threshold(self):
        """Verify low confidence detected when below 0.90 (T196)."""
        handler = LowConfidenceHandler(confidence_threshold=0.90)

        scores = {
            "language_detection": 0.95,
            "framework_detection": 0.85,  # Below threshold
            "pattern_discovery": 0.92,
            "convention_learning": 0.80,  # Below threshold - adjusted for overall < 0.90
        }

        analysis = handler.analyze_confidence(scores)

        assert analysis.overall_confidence < 0.90
        assert "framework_detection" in analysis.low_confidence_phases
        assert "convention_learning" in analysis.low_confidence_phases

    def test_low_confidence_recommendations_generated(self):
        """Verify recommendations generated for low confidence (T197)."""
        handler = LowConfidenceHandler()

        scores = {
            "language_detection": 0.65,  # Very low
            "framework_detection": 0.88,
            "pattern_discovery": 0.92,
            "convention_learning": 0.78,
        }

        analysis = handler.analyze_confidence(scores)

        assert len(analysis.recommendations) > 0
        assert any("language" in rec.lower() for rec in analysis.recommendations)

    def test_can_proceed_if_overall_above_70_percent(self):
        """Verify can proceed if overall >= 0.70 (T198)."""
        handler = LowConfidenceHandler(confidence_threshold=0.90)

        # Overall: (0.60 + 0.75 + 0.85 + 0.90) / 4 = 0.775 > 0.70
        scores = {
            "language_detection": 0.60,
            "framework_detection": 0.75,
            "pattern_discovery": 0.85,
            "convention_learning": 0.90,
        }

        analysis = handler.analyze_confidence(scores)

        assert analysis.can_proceed is True
        assert analysis.overall_confidence >= 0.70

    def test_cannot_proceed_if_overall_below_70_percent(self):
        """Verify cannot proceed if overall < 0.70 (T199)."""
        handler = LowConfidenceHandler(confidence_threshold=0.90)

        # Overall: (0.40 + 0.50 + 0.60 + 0.65) / 4 = 0.5375 < 0.70
        scores = {
            "language_detection": 0.40,
            "framework_detection": 0.50,
            "pattern_discovery": 0.60,
            "convention_learning": 0.65,
        }

        analysis = handler.analyze_confidence(scores)

        assert analysis.can_proceed is False

    def test_high_confidence_no_warnings(self):
        """Verify no warnings when all phases confident (T200)."""
        handler = LowConfidenceHandler(confidence_threshold=0.90)

        scores = {
            "language_detection": 0.96,
            "framework_detection": 0.94,
            "pattern_discovery": 0.95,
            "convention_learning": 0.93,
        }

        analysis = handler.analyze_confidence(scores)

        assert len(analysis.low_confidence_phases) == 0
        assert analysis.can_proceed is True
        assert len(analysis.recommendations) == 0
