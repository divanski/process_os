r"""
Structure convention analyzer for learning directory and namespace patterns.

This module analyzes code structure to detect conventions:
- Namespace patterns (e.g., App\Services\{Domain})
- Directory structure patterns
- Import/use statement ordering
"""

import re
from pathlib import Path
from collections import Counter
from typing import Optional

from process_os.architecture import ProgrammingLanguage, ProjectArchitecture


class StructureAnalyzer:
    """Analyzes structural conventions in source code.

    Detects and analyzes:
    - Namespace/module patterns
    - Directory structure patterns
    - Import/use statement ordering
    """

    def __init__(self):
        """Initialize the structure analyzer."""
        pass

    def analyze_namespace_pattern(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> Optional[str]:
        """Analyze namespace/module naming patterns.

        Args:
            file_paths: List of source files to analyze
            language: Programming language

        Returns:
            Detected namespace pattern or None
        """
        namespaces = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            namespace = self._extract_namespace(file_path, language)
            if namespace:
                namespaces.append(namespace)

        if not namespaces:
            return None

        # Extract common pattern from namespaces
        return self._extract_pattern_from_namespaces(namespaces)

    def analyze_directory_pattern(
        self, project_path: Path, architecture: ProjectArchitecture
    ) -> Optional[str]:
        """Analyze directory structure patterns.

        Args:
            project_path: Root path of the project
            architecture: Project architecture information

        Returns:
            Detected directory pattern or None
        """
        # Look for common service/integration directories
        directories = []

        if project_path.exists():
            for path in project_path.rglob("*"):
                if path.is_dir():
                    rel_path = path.relative_to(project_path)
                    rel_str = str(rel_path).replace("\\", "/")

                    # Look for patterns in common directories
                    if any(
                        keyword in rel_str.lower()
                        for keyword in ["service", "adapter", "integration", "module"]
                    ):
                        directories.append(rel_str)

        if not directories:
            return None

        # Extract common pattern
        return self._extract_common_pattern(directories)

    def analyze_import_ordering(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> Optional[dict]:
        """Analyze import/use statement ordering patterns.

        Args:
            file_paths: List of source files to analyze
            language: Programming language

        Returns:
            Dict describing import ordering or None
        """
        import_orders = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            ordering = self._extract_import_ordering(file_path, language)
            if ordering:
                import_orders.append(ordering)

        if not import_orders:
            return None

        # Analyze patterns
        return self._analyze_import_patterns(import_orders)

    def _extract_namespace(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> Optional[str]:
        """Extract namespace from a file.

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            Namespace string or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return None

        if language == ProgrammingLanguage.PHP:
            # Match PHP namespace
            pattern = re.compile(r"namespace\s+([\w\\]+);")
            match = pattern.search(content)
            if match:
                return match.group(1)

        elif language == ProgrammingLanguage.PYTHON:
            # For Python, use the file path as module path
            return str(file_path.parent).replace("\\", ".")

        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            # JavaScript doesn't have explicit namespaces, use package name
            return str(file_path.parent).replace("\\", "/")

        return None

    def _extract_import_ordering(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> Optional[str]:
        """Extract import statement ordering from a file.

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            Ordering strategy string
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return None

        imports = []

        if language == ProgrammingLanguage.PHP:
            # Extract use statements
            pattern = re.compile(r"use\s+([\w\\]+)")
            matches = pattern.findall(content)
            imports.extend(matches)

        elif language == ProgrammingLanguage.PYTHON:
            # Extract import statements
            pattern = re.compile(r"^(?:import|from)\s+", re.MULTILINE)
            matches = pattern.findall(content)
            imports.extend(matches)

        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            # Extract import statements
            pattern = re.compile(r"import\s+")
            matches = pattern.findall(content)
            imports.extend(matches)

        if not imports:
            return None

        # Determine ordering: check if alphabetical, grouped, etc.
        if imports == sorted(imports):
            return "alphabetical"
        elif self._is_grouped(imports):
            return "grouped"
        else:
            return "custom"

    def _extract_pattern_from_namespaces(
        self, namespaces: list[str]
    ) -> Optional[str]:
        """Extract a common pattern from multiple namespaces.

        Args:
            namespaces: List of namespace strings

        Returns:
            Pattern string with {variable} placeholders
        """
        if not namespaces:
            return None

        # Find common prefix
        if len(namespaces) == 1:
            return namespaces[0]

        # Find the longest common prefix
        prefix = ""
        for i, char in enumerate(namespaces[0]):
            if all(ns[i:i+1] == char for ns in namespaces):
                prefix += char
            else:
                break

        return prefix

    def _extract_common_pattern(self, directories: list[str]) -> Optional[str]:
        """Extract common pattern from directory list.

        Args:
            directories: List of directory paths

        Returns:
            Pattern string with {variable} placeholders
        """
        if not directories:
            return None

        if len(directories) == 1:
            return directories[0]

        # Find common parts
        parts_list = [d.split("/") for d in directories]
        common_parts = []

        if parts_list:
            for i in range(len(parts_list[0])):
                part_set = {parts[i] for parts in parts_list if i < len(parts)}
                if len(part_set) == 1:
                    common_parts.append(list(part_set)[0])
                else:
                    # Different parts at this level
                    common_parts.append("{type}")
                    break

        return "/".join(common_parts) if common_parts else None

    def _is_grouped(self, imports: list[str]) -> bool:
        """Check if imports are grouped (separated by type).

        Args:
            imports: List of import statements

        Returns:
            True if imports appear grouped
        """
        # Simplified: check if there are clusters of related imports
        if len(imports) < 3:
            return False

        # Count transitions (when import type changes)
        transitions = 0
        prev_type = None

        for imp in imports:
            # Classify import by prefix
            if imp.startswith("from "):
                imp_type = "from"
            elif imp.startswith("import "):
                imp_type = "import"
            else:
                imp_type = "other"

            if prev_type and prev_type != imp_type:
                transitions += 1
            prev_type = imp_type

        # If there are clear transitions, likely grouped
        return transitions > 0

    def _analyze_import_patterns(self, import_orders: list[Optional[str]]) -> dict:
        """Analyze patterns from multiple import orders.

        Args:
            import_orders: List of import ordering strategies

        Returns:
            Dict with analysis results
        """
        if not import_orders:
            return {}

        counter = Counter(import_orders)
        most_common = counter.most_common(1)

        return {
            "dominant_strategy": most_common[0][0] if most_common else "custom",
            "consistency": most_common[0][1] / len(import_orders) if most_common else 0.0,
        }
