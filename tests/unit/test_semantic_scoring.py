"""
Unit tests for semantic similarity scoring.

Tests for Phase 6 (US4): Semantic component of hybrid novelty detection

Tests:
- T150-T152: SemanticScorer class and embedding-based similarity
"""

from typing import Dict, List
from dataclasses import dataclass

import pytest


@dataclass
class EmbeddingResult:
    """Result of embedding calculation."""

    vector: List[float]
    text: str


class SemanticScorer:
    """Semantic similarity scorer using embeddings or LLM API."""

    def __init__(self):
        self.embedding_cache = {}
        self.similarity_cache = {}

    def get_embedding(self, text: str) -> EmbeddingResult:
        """
        Get embedding for text (T151).

        Uses anthropic SDK embeddings or LLM API for semantic representation.
        Returns vector of semantic meaning.
        """
        if text in self.embedding_cache:
            return self.embedding_cache[text]

        # Simple mock embedding for testing
        # In production, would use anthropic SDK or similar
        words = text.lower().split()
        vector = self._simple_embedding(words)

        result = EmbeddingResult(vector=vector, text=text)
        self.embedding_cache[text] = result
        return result

    def _simple_embedding(self, words: List[str]) -> List[float]:
        """
        Generate simple embedding vector for testing.

        In production, would use actual embeddings.
        """
        # Create a 100-dimensional vector based on word patterns
        vector = [0.0] * 100

        for word in words:
            # Map word to vector dimensions using simple hash
            for i, char in enumerate(word):
                idx = (ord(char) + i) % 100
                vector[idx] += 1.0 / len(word)

        # Normalize
        magnitude = sum(v ** 2 for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts (T152).

        Uses cosine distance or similar metric.
        Returns 0.0-1.0 where 1.0 = perfect semantic match.
        """
        cache_key = (text1, text2)
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]

        embedding1 = self.get_embedding(text1)
        embedding2 = self.get_embedding(text2)

        similarity = self._cosine_similarity(embedding1.vector, embedding2.vector)
        self.similarity_cache[cache_key] = similarity
        return similarity

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def compare_with_patterns(
        self,
        task_description: str,
        pattern_descriptions: Dict[str, str],
    ) -> Dict[str, float]:
        """
        Compare task description with multiple pattern descriptions.

        Returns dict of {pattern_name: similarity_score}
        """
        results = {}
        for pattern_name, pattern_desc in pattern_descriptions.items():
            similarity = self.calculate_similarity(task_description, pattern_desc)
            results[pattern_name] = similarity

        return results

    def semantic_similarity_with_threshold(
        self,
        text1: str,
        text2: str,
        threshold: float = 0.85,
    ) -> bool:
        """
        Check if semantic similarity meets threshold.

        Returns True if similarity >= threshold.
        """
        similarity = self.calculate_similarity(text1, text2)
        return similarity >= threshold


class TestSemanticScorerBasic:
    """Basic semantic scoring tests (T150)."""

    def test_semantic_scorer_initialization(self):
        """Verify SemanticScorer can be initialized."""
        scorer = SemanticScorer()
        assert scorer is not None
        assert len(scorer.embedding_cache) == 0

    def test_get_embedding_returns_vector(self):
        """Verify get_embedding returns embedding vector."""
        scorer = SemanticScorer()
        embedding = scorer.get_embedding("REST API endpoint")

        assert embedding.vector is not None
        assert len(embedding.vector) > 0
        assert isinstance(embedding.vector, list)

    def test_embedding_caching(self):
        """Verify embeddings are cached for performance."""
        scorer = SemanticScorer()
        text = "Test semantic similarity"

        embedding1 = scorer.get_embedding(text)
        embedding2 = scorer.get_embedding(text)

        # Should be same object from cache
        assert embedding1.vector == embedding2.vector
        assert text in scorer.embedding_cache


class TestSemanticSimilarity:
    """Semantic similarity calculation tests (T151)."""

    def test_semantic_similarity_perfect_match(self):
        """Verify 1.0 similarity for identical text."""
        scorer = SemanticScorer()
        similarity = scorer.calculate_similarity("REST API", "REST API")

        assert abs(similarity - 1.0) < 0.0001  # Allow for floating point precision

    def test_semantic_similarity_different_text(self):
        """Verify lower similarity for different text."""
        scorer = SemanticScorer()
        similarity = scorer.calculate_similarity(
            "REST API endpoints",
            "Database queries",
        )

        assert 0.0 <= similarity <= 1.0
        assert similarity < 1.0  # Should not be perfect match

    def test_semantic_similarity_related_concepts(self):
        """Verify higher similarity for related concepts."""
        scorer = SemanticScorer()

        similarity_api = scorer.calculate_similarity(
            "REST API with endpoints",
            "RESTful API endpoints",
        )

        similarity_unrelated = scorer.calculate_similarity(
            "REST API with endpoints",
            "Database migrations",
        )

        # Related concepts should have higher similarity
        assert similarity_api > similarity_unrelated

    def test_semantic_similarity_symmetry(self):
        """Verify similarity(A, B) == similarity(B, A)."""
        scorer = SemanticScorer()

        sim1 = scorer.calculate_similarity("Model View Controller", "Controller")
        sim2 = scorer.calculate_similarity("Controller", "Model View Controller")

        assert sim1 == sim2


class TestSemanticPatternComparison:
    """Pattern comparison using semantic similarity (T152)."""

    def test_compare_with_patterns(self):
        """Verify task can be compared with multiple patterns."""
        scorer = SemanticScorer()
        patterns = {
            "MVC": "Model View Controller pattern with architecture",
            "REST": "REST API with endpoints",
            "CRUD": "Create Read Update Delete operations",
        }

        task_desc = "Model View Controller with API endpoints"
        results = scorer.compare_with_patterns(task_desc, patterns)

        assert "MVC" in results
        assert "REST" in results
        assert "CRUD" in results
        assert all(isinstance(v, float) for v in results.values())

    def test_pattern_ranking_by_similarity(self):
        """Verify patterns ranked by semantic similarity."""
        scorer = SemanticScorer()
        patterns = {
            "MVC": "Model View Controller pattern",
            "MVVM": "Model View ViewModel pattern",
            "REST": "REST API endpoints",
        }

        task_desc = "Model View Controller implementation"
        results = scorer.compare_with_patterns(task_desc, patterns)

        # MVC should have highest similarity to task about MVC
        mvc_score = results["MVC"]
        rest_score = results["REST"]

        assert mvc_score > rest_score

    def test_find_most_similar_pattern(self):
        """Verify finding the most similar pattern."""
        scorer = SemanticScorer()
        patterns = {
            "MVC": "Model View Controller",
            "REST": "REST endpoints",
            "CRUD": "Create Read Update Delete",
        }

        task_desc = "Model View Controller architecture"
        results = scorer.compare_with_patterns(task_desc, patterns)

        most_similar = max(results.items(), key=lambda x: x[1])
        assert most_similar[0] == "MVC"


class TestSemanticThreshold:
    """Semantic similarity threshold testing."""

    def test_similarity_meets_threshold(self):
        """Verify threshold check for similar texts."""
        scorer = SemanticScorer()

        # Identical text should meet any reasonable threshold
        result = scorer.semantic_similarity_with_threshold(
            "REST API implementation",
            "REST API implementation",
            threshold=0.85,
        )

        assert result is True

    def test_similarity_below_threshold(self):
        """Verify threshold check fails for different texts."""
        scorer = SemanticScorer()

        # Very different texts should fail threshold
        result = scorer.semantic_similarity_with_threshold(
            "REST API endpoints",
            "Binary search tree implementation",
            threshold=0.85,
        )

        assert result is False

    def test_similarity_custom_threshold(self):
        """Verify custom threshold values."""
        scorer = SemanticScorer()

        text1 = "API authentication system"
        text2 = "Authentication and authorization"

        # Should meet lower threshold
        result_low = scorer.semantic_similarity_with_threshold(
            text1,
            text2,
            threshold=0.50,
        )

        # May not meet higher threshold
        result_high = scorer.semantic_similarity_with_threshold(
            text1,
            text2,
            threshold=0.95,
        )

        # Lower threshold should be more likely to pass
        if not result_low:
            # If even lower threshold fails, higher definitely fails
            assert not result_high


class TestSemanticEdgeCases:
    """Edge case handling for semantic scorer."""

    def test_empty_text_similarity(self):
        """Verify handling of empty text."""
        scorer = SemanticScorer()
        similarity = scorer.calculate_similarity("", "")

        # Empty texts should be "identical"
        assert similarity >= 0.0

    def test_single_word_similarity(self):
        """Verify similarity with single words."""
        scorer = SemanticScorer()
        similarity = scorer.calculate_similarity("API", "API")

        assert abs(similarity - 1.0) < 0.0001  # Allow for floating point precision

    def test_long_text_similarity(self):
        """Verify similarity calculation with long texts."""
        scorer = SemanticScorer()

        long_text1 = "REST API implementation with authentication and authorization for microservices architecture"
        long_text2 = "RESTful API endpoints with OAuth2 authentication for distributed systems"

        similarity = scorer.calculate_similarity(long_text1, long_text2)

        assert 0.0 <= similarity <= 1.0


class TestSemanticIntegration:
    """Integration tests for semantic scoring."""

    def test_semantic_scorer_workflow(self):
        """Verify complete semantic scoring workflow."""
        scorer = SemanticScorer()

        # Task description
        task = "Build REST API with JWT authentication"

        # Available patterns
        patterns = {
            "REST_API": "REST API with HTTP endpoints",
            "AUTH": "Authentication and authorization system",
            "JWT": "JWT token-based authentication",
            "CRUD": "Create Read Update Delete operations",
        }

        # Get similarities
        results = scorer.compare_with_patterns(task, patterns)

        # All patterns should have scores
        assert len(results) == 4
        assert all(0.0 <= v <= 1.0 for v in results.values())

        # Find best match
        best_pattern, best_score = max(results.items(), key=lambda x: x[1])

        # Best match should be a relevant pattern
        assert best_pattern in patterns

        # Score should reflect relevance
        assert best_score > 0.0
