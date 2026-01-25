"""
Semantic and structural scoring for novelty detection.

SemanticScorer: 60% weight - text and description similarity
StructuralScorer: 40% weight - code structure and file organization
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Result of embedding calculation."""

    vector: List[float]
    text: str


class SemanticScorer:
    """
    Semantic similarity scorer using embeddings or LLM API.

    Uses 60% weight in hybrid novelty detection.
    Compares task descriptions with pattern descriptions semantically.
    """

    def __init__(self):
        """Initialize SemanticScorer."""
        self.embedding_cache = {}
        self.similarity_cache = {}

    def get_embedding(self, text: str) -> EmbeddingResult:
        """
        Get embedding for text.

        Uses anthropic SDK embeddings or LLM API for semantic representation.
        Returns vector of semantic meaning.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with vector representation
        """
        if text in self.embedding_cache:
            return self.embedding_cache[text]

        # Create embedding vector based on text content
        words = text.lower().split()
        vector = self._generate_embedding(words)

        result = EmbeddingResult(vector=vector, text=text)
        self.embedding_cache[text] = result
        return result

    def _generate_embedding(self, words: List[str]) -> List[float]:
        """
        Generate embedding vector for text.

        In production, would use actual embeddings from anthropic SDK.
        For now, generates deterministic vector based on word content.

        Args:
            words: Tokenized words from text

        Returns:
            Embedding vector (100-dimensional)
        """
        # Create 100-dimensional vector
        vector = [0.0] * 100

        # Map words to vector dimensions
        for word in words:
            for i, char in enumerate(word):
                idx = (ord(char) + i) % 100
                vector[idx] += 1.0 / len(word)

        # Normalize vector
        magnitude = sum(v ** 2 for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.

        Uses cosine distance metric.
        Returns 0.0-1.0 where 1.0 = perfect semantic match.

        Args:
            text1: First text to compare
            text2: Second text to compare

        Returns:
            Similarity score 0.0-1.0
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
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score 0.0-1.0
        """
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

        Args:
            task_description: Description of the task
            pattern_descriptions: Dict mapping pattern names to descriptions

        Returns:
            Dict of {pattern_name: similarity_score}
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

        Args:
            text1: First text
            text2: Second text
            threshold: Minimum similarity required

        Returns:
            True if similarity >= threshold
        """
        similarity = self.calculate_similarity(text1, text2)
        return similarity >= threshold


class StructuralScorer:
    """
    Structural similarity scorer for code organization.

    Uses 40% weight in hybrid novelty detection.
    Analyzes code structure, file organization, and architectural patterns.
    """

    def __init__(self):
        """Initialize StructuralScorer."""
        self.structure_cache = {}
        self.similarity_cache = {}

    def analyze_structure(self, structure: str) -> Dict[str, int]:
        """
        Analyze code structure and count key elements.

        Args:
            structure: Code structure representation

        Returns:
            Dict of {element_type: count}
        """
        if structure in self.structure_cache:
            return self.structure_cache[structure]

        analysis = {
            "classes": structure.lower().count("class"),
            "functions": structure.lower().count("def") + structure.lower().count("function"),
            "modules": structure.lower().count("module"),
            "controllers": structure.lower().count("controller"),
            "models": structure.lower().count("model"),
            "interfaces": structure.lower().count("interface"),
            "services": structure.lower().count("service"),
            "repositories": structure.lower().count("repository"),
            "decorators": structure.lower().count("@"),
            "imports": structure.lower().count("import"),
        }

        self.structure_cache[structure] = analysis
        return analysis

    def calculate_structural_similarity(
        self,
        structure1: str,
        structure2: str,
    ) -> float:
        """
        Calculate structural similarity between two code structures.

        Compares frequency of structural elements.
        Returns 0.0-1.0 where 1.0 = identical structure.

        Args:
            structure1: First structure
            structure2: Second structure

        Returns:
            Similarity score 0.0-1.0
        """
        cache_key = (structure1, structure2)
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]

        analysis1 = self.analyze_structure(structure1)
        analysis2 = self.analyze_structure(structure2)

        # Compare element counts
        total_diff = 0
        total_count = 0

        for element_type in analysis1:
            count1 = analysis1[element_type]
            count2 = analysis2.get(element_type, 0)

            total_diff += abs(count1 - count2)
            total_count += max(count1, count2)

        # Calculate similarity (1.0 if identical, 0.0 if completely different)
        if total_count == 0:
            similarity = 1.0
        else:
            similarity = 1.0 - (total_diff / (total_count * 2))

        self.similarity_cache[cache_key] = similarity
        return similarity

    def compare_with_patterns(
        self,
        task_structure: str,
        pattern_structures: Dict[str, str],
    ) -> Dict[str, float]:
        """
        Compare task structure with multiple pattern structures.

        Args:
            task_structure: Code structure of the task
            pattern_structures: Dict mapping pattern names to structures

        Returns:
            Dict of {pattern_name: similarity_score}
        """
        results = {}

        for pattern_name, pattern_struct in pattern_structures.items():
            similarity = self.calculate_structural_similarity(task_structure, pattern_struct)
            results[pattern_name] = similarity

        return results

    def identify_architectural_pattern(self, structure: str) -> Optional[str]:
        """
        Identify potential architectural pattern from structure.

        Args:
            structure: Code structure

        Returns:
            Name of detected pattern or None
        """
        analysis = self.analyze_structure(structure)

        # Simple pattern detection
        if analysis["models"] > 0 and analysis["controllers"] > 0 and analysis["views"] == 0:
            return "MVC"
        elif analysis["services"] > analysis["repositories"]:
            return "Service Layer"
        elif analysis["decorators"] > 0:
            return "Decorator Pattern"
        elif analysis["interfaces"] > analysis["classes"]:
            return "Interface-based"

        return None

    def structural_similarity_with_threshold(
        self,
        structure1: str,
        structure2: str,
        threshold: float = 0.75,
    ) -> bool:
        """
        Check if structural similarity meets threshold.

        Args:
            structure1: First structure
            structure2: Second structure
            threshold: Minimum similarity required

        Returns:
            True if similarity >= threshold
        """
        similarity = self.calculate_structural_similarity(structure1, structure2)
        return similarity >= threshold
