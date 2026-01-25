"""
Storage handler for PatternLibrary entities.

Implements:
- T-NEW-008: PatternLibrary storage in .processos/patterns/
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Pattern:
    """
    Represents an architectural or code pattern discovered in the codebase.

    Patterns are reusable solutions to common problems.
    """

    def __init__(
        self,
        pattern_id: str,
        name: str,
        category: str,
        description: str,
    ):
        """
        Initialize pattern.

        Args:
            pattern_id: Unique pattern identifier
            name: Pattern name
            category: Pattern category (e.g., 'architectural', 'code', 'convention')
            description: Pattern description
        """
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.description = description
        self.discovered_at = datetime.now().isoformat()
        self.occurrences: List[Dict[str, Any]] = []
        self.confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "discovered_at": self.discovered_at,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        """Create pattern from dictionary."""
        pattern = cls(
            pattern_id=data["pattern_id"],
            name=data["name"],
            category=data["category"],
            description=data["description"],
        )
        pattern.discovered_at = data.get("discovered_at", pattern.discovered_at)
        pattern.occurrences = data.get("occurrences", [])
        pattern.confidence = data.get("confidence", 0.0)
        return pattern


class PatternLibrary:
    """
    Maintains a library of patterns discovered in a project.

    Patterns are stored with occurrences, confidence scores, and reusability info.
    """

    def __init__(self, project_id: str):
        """
        Initialize pattern library.

        Args:
            project_id: Project identifier
        """
        self.project_id = project_id
        self.created_at = datetime.now().isoformat()
        self.patterns: Dict[str, Pattern] = {}

    def add_pattern(
        self,
        name: str,
        category: str,
        description: str,
        confidence: float = 0.0,
    ) -> Pattern:
        """
        Add pattern to library.

        Args:
            name: Pattern name
            category: Pattern category
            description: Pattern description
            confidence: Initial confidence score

        Returns:
            Added pattern
        """
        pattern_id = str(uuid4())
        pattern = Pattern(
            pattern_id=pattern_id,
            name=name,
            category=category,
            description=description,
        )
        pattern.confidence = confidence
        self.patterns[pattern_id] = pattern
        return pattern

    def record_occurrence(
        self,
        pattern_id: str,
        file_path: str,
        line_number: int,
        snippet: str,
    ) -> bool:
        """
        Record occurrence of pattern.

        Args:
            pattern_id: Pattern identifier
            file_path: File path where pattern found
            line_number: Line number of occurrence
            snippet: Code snippet

        Returns:
            True if recorded, False if pattern not found
        """
        if pattern_id not in self.patterns:
            return False

        pattern = self.patterns[pattern_id]
        pattern.occurrences.append(
            {
                "file": file_path,
                "line": line_number,
                "snippet": snippet,
                "found_at": datetime.now().isoformat(),
            }
        )

        return True

    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """
        Get pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Pattern or None if not found
        """
        return self.patterns.get(pattern_id)

    def get_patterns_by_category(self, category: str) -> List[Pattern]:
        """
        Get all patterns in category.

        Args:
            category: Pattern category

        Returns:
            List of patterns
        """
        return [p for p in self.patterns.values() if p.category == category]

    def get_all_patterns(self) -> List[Pattern]:
        """
        Get all patterns in library.

        Returns:
            List of all patterns
        """
        return list(self.patterns.values())

    def get_pattern_count(self) -> int:
        """
        Get total number of patterns.

        Returns:
            Pattern count
        """
        return len(self.patterns)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "created_at": self.created_at,
            "patterns": {
                pattern_id: pattern.to_dict()
                for pattern_id, pattern in self.patterns.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternLibrary":
        """Create library from dictionary."""
        library = cls(project_id=data["project_id"])
        library.created_at = data.get("created_at", library.created_at)

        for pattern_id, pattern_data in data.get("patterns", {}).items():
            pattern = Pattern.from_dict(pattern_data)
            library.patterns[pattern_id] = pattern

        return library


class PatternLibraryStorageManager:
    """
    Manages persistence of PatternLibrary objects.

    Stores libraries in .processos/patterns/ directory.
    """

    def __init__(self, patterns_dir: Optional[Path] = None):
        """
        Initialize pattern storage manager.

        Args:
            patterns_dir: Directory for pattern storage
        """
        self.patterns_dir = Path(patterns_dir) if patterns_dir else Path.cwd()
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self.libraries: Dict[str, PatternLibrary] = {}

    def create_library(self, project_id: str) -> PatternLibrary:
        """
        Create and store new pattern library.

        Args:
            project_id: Project identifier

        Returns:
            Created library
        """
        library = PatternLibrary(project_id=project_id)
        self.libraries[project_id] = library
        self._save_library(library)
        return library

    def get_library(self, project_id: str) -> Optional[PatternLibrary]:
        """
        Get pattern library for project.

        Args:
            project_id: Project identifier

        Returns:
            Library or None if not found
        """
        # Check memory first
        if project_id in self.libraries:
            return self.libraries[project_id]

        # Load from disk
        library_path = self.patterns_dir / f"{project_id}.json"
        if library_path.exists():
            try:
                data = json.loads(library_path.read_text())
                library = PatternLibrary.from_dict(data)
                self.libraries[project_id] = library
                return library
            except (json.JSONDecodeError, KeyError):
                return None

        return None

    def save_library(self, library: PatternLibrary) -> None:
        """
        Save library to disk.

        Args:
            library: Library to save
        """
        self.libraries[library.project_id] = library
        self._save_library(library)

    def delete_library(self, project_id: str) -> bool:
        """
        Delete library.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted, False if not found
        """
        # Remove from memory
        if project_id in self.libraries:
            del self.libraries[project_id]

        # Remove from disk
        library_path = self.patterns_dir / f"{project_id}.json"
        if library_path.exists():
            library_path.unlink()
            return True

        return False

    def get_all_libraries(self) -> List[PatternLibrary]:
        """
        Get all pattern libraries.

        Returns:
            List of libraries
        """
        libraries = []

        for library_file in self.patterns_dir.glob("*.json"):
            project_id = library_file.stem
            library = self.get_library(project_id)
            if library:
                libraries.append(library)

        return libraries

    def _save_library(self, library: PatternLibrary) -> None:
        """
        Save library to disk.

        Args:
            library: Library to save
        """
        library_path = self.patterns_dir / f"{library.project_id}.json"
        library_path.write_text(json.dumps(library.to_dict(), indent=2))

    def __repr__(self) -> str:
        """String representation."""
        return f"PatternLibraryStorageManager(patterns_dir={self.patterns_dir})"
