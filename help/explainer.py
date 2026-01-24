"""
ProcessOS Help Explainer

Context-aware help system that explains ProcessOS concepts,
artifacts, commands, and error messages.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class HelpCategory(Enum):
    """Category of help topic."""
    CONCEPT = "concept"
    ARTIFACT = "artifact"
    COMMAND = "command"
    ERROR = "error"


@dataclass
class HelpTopic:
    """
    Structured help content for a ProcessOS topic.

    Attributes:
        id: Topic identifier (e.g., "binding", "playbook", "E001")
        title: Human-readable title
        category: Type of topic (concept, artifact, command, error)
        summary: One-line description
        description: Full description (supports markdown)
        examples: Usage examples
        related: Related topic IDs
        file_patterns: For artifact topics, file patterns this explains
        error_codes: For error topics, error codes this addresses
        remediation: For error topics, how to fix
    """
    id: str
    title: str
    category: HelpCategory
    summary: str
    description: str
    examples: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    error_codes: List[str] = field(default_factory=list)
    remediation: Optional[str] = None


class HelpExplainer:
    """
    Provides context-aware help for ProcessOS topics.

    Supports looking up help by:
    - Topic ID (e.g., "binding", "playbook")
    - Error code (e.g., "E001", "E002")
    - File pattern (e.g., "config.yaml", "manifest.yaml")
    """

    def __init__(self):
        """Initialize the help explainer with built-in topics."""
        self._topics: Dict[str, HelpTopic] = {}
        self._error_index: Dict[str, str] = {}  # error_code -> topic_id
        self._file_index: Dict[str, str] = {}   # pattern -> topic_id
        self._load_builtin_topics()

    def _load_builtin_topics(self) -> None:
        """Load built-in help topics."""
        # Topics will be registered by the help/topics/ modules
        pass

    def register(self, topic: HelpTopic) -> None:
        """
        Register a help topic.

        Args:
            topic: The help topic to register
        """
        self._topics[topic.id] = topic

        # Index error codes
        for code in topic.error_codes:
            self._error_index[code] = topic.id

        # Index file patterns
        for pattern in topic.file_patterns:
            self._file_index[pattern] = topic.id

    def get(self, topic_id: str) -> Optional[HelpTopic]:
        """
        Get a help topic by ID.

        Args:
            topic_id: The topic identifier

        Returns:
            HelpTopic if found, None otherwise
        """
        return self._topics.get(topic_id)

    def get_by_error(self, error_code: str) -> Optional[HelpTopic]:
        """
        Get help topic for an error code.

        Args:
            error_code: The error code (e.g., "E001")

        Returns:
            HelpTopic if found, None otherwise
        """
        topic_id = self._error_index.get(error_code)
        if topic_id:
            return self._topics.get(topic_id)
        return None

    def get_by_file(self, filename: str) -> Optional[HelpTopic]:
        """
        Get help topic that explains a file.

        Args:
            filename: The filename to look up

        Returns:
            HelpTopic if found, None otherwise
        """
        # Try exact match first
        topic_id = self._file_index.get(filename)
        if topic_id:
            return self._topics.get(topic_id)

        # Try pattern matching
        for pattern, tid in self._file_index.items():
            if self._matches_pattern(filename, pattern):
                return self._topics.get(tid)

        return None

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches a pattern (simple glob support)."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

    def list_topics(self, category: Optional[HelpCategory] = None) -> List[HelpTopic]:
        """
        List all topics, optionally filtered by category.

        Args:
            category: Optional category to filter by

        Returns:
            List of matching topics
        """
        topics = list(self._topics.values())
        if category:
            topics = [t for t in topics if t.category == category]
        return sorted(topics, key=lambda t: t.id)

    def search(self, query: str) -> List[HelpTopic]:
        """
        Search topics by query string.

        Args:
            query: Search query

        Returns:
            List of matching topics
        """
        query = query.lower()
        results = []
        for topic in self._topics.values():
            if (query in topic.id.lower() or
                query in topic.title.lower() or
                query in topic.summary.lower() or
                query in topic.description.lower()):
                results.append(topic)
        return sorted(results, key=lambda t: t.id)

    def format_topic(self, topic: HelpTopic, verbose: bool = False) -> str:
        """
        Format a topic for display.

        Args:
            topic: The topic to format
            verbose: Whether to include full description

        Returns:
            Formatted string
        """
        lines = [
            f"# {topic.title}",
            "",
            f"**Category**: {topic.category.value}",
            "",
            topic.summary,
        ]

        if verbose:
            lines.extend([
                "",
                "## Description",
                "",
                topic.description,
            ])

            if topic.examples:
                lines.extend([
                    "",
                    "## Examples",
                    "",
                ])
                for example in topic.examples:
                    lines.append(f"  {example}")

            if topic.remediation:
                lines.extend([
                    "",
                    "## How to Fix",
                    "",
                    topic.remediation,
                ])

            if topic.related:
                lines.extend([
                    "",
                    "## Related Topics",
                    "",
                    f"  {', '.join(topic.related)}",
                ])

        return "\n".join(lines)


# Global help explainer instance
_explainer: Optional[HelpExplainer] = None


def get_explainer() -> HelpExplainer:
    """Get the global help explainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = HelpExplainer()
    return _explainer
