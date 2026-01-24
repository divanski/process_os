"""
Pattern matcher for matching user requests to discovered patterns.

This module implements pattern matching logic to find the best-fitting
integration pattern from a set of discovered patterns based on user input.
"""

from typing import Optional

from process_os.patterns.types import IntegrationPattern
from process_os.patterns.errors import PatternDiscoveryError


class PatternMatcher:
    """Matches user requests to discovered integration patterns.

    Given a set of discovered patterns and a user request (integration type),
    selects the best matching pattern or suggests fallback options.

    Example:
        >>> matcher = PatternMatcher()
        >>> pattern = matcher.match("courier_dhl", discovered_patterns)
        >>> print(pattern.pattern_name)
    """

    def __init__(self):
        """Initialize the pattern matcher."""
        pass

    def match(
        self,
        user_request: str,
        patterns: list[IntegrationPattern],
    ) -> Optional[IntegrationPattern]:
        """Match user request to the best fitting pattern.

        Selects from available patterns based on:
        1. Exact match on integration type
        2. Similarity of integration types
        3. Highest confidence score if multiple matches

        Args:
            user_request: User's request string (e.g., "courier_dhl", "payment")
            patterns: List of discovered patterns to match against

        Returns:
            Best matching IntegrationPattern or None if no good match

        Raises:
            PatternDiscoveryError: If matching fails unexpectedly
        """
        if not patterns:
            return None

        # Normalize the request
        request_lower = user_request.lower().replace("_", " ").replace("-", " ")

        # Score each pattern
        scored_patterns = []
        for pattern in patterns:
            score = self._score_pattern(request_lower, pattern)
            if score > 0:
                scored_patterns.append((score, pattern))

        # Return highest scoring pattern
        if scored_patterns:
            scored_patterns.sort(key=lambda x: x[0], reverse=True)
            return scored_patterns[0][1]

        return None

    def match_or_default(
        self,
        user_request: str,
        patterns: list[IntegrationPattern],
        default_pattern: Optional[IntegrationPattern] = None,
    ) -> IntegrationPattern:
        """Match user request with fallback to default pattern.

        Args:
            user_request: User's request string
            patterns: List of discovered patterns
            default_pattern: Pattern to use if no match found

        Returns:
            Matched pattern or default pattern

        Raises:
            PatternDiscoveryError: If no match and no default provided
        """
        matched = self.match(user_request, patterns)

        if matched:
            return matched

        if default_pattern:
            return default_pattern

        raise PatternDiscoveryError(
            f"Could not match request '{user_request}' and no default pattern provided"
        )

    def _score_pattern(self, request: str, pattern: IntegrationPattern) -> float:
        """Score how well a pattern matches the request.

        Args:
            request: Normalized request string
            pattern: Pattern to score

        Returns:
            Score between 0 and 1
        """
        score = 0.0

        pattern_type = pattern.integration_type.lower()
        pattern_name = pattern.pattern_name.lower()

        # Exact match on integration type
        if pattern_type == request:
            score += 0.9

        # Substring match on integration type
        if pattern_type in request or request in pattern_type:
            score += 0.6

        # Substring match on pattern name
        if pattern_name in request or request in pattern_name:
            score += 0.3

        # Bonus for high confidence
        if pattern.confidence >= 0.9:
            score += 0.1
        elif pattern.confidence >= 0.7:
            score += 0.05

        return min(score, 1.0)
