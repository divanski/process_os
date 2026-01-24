"""
Naming convention analyzer for learning naming patterns from code.

This module analyzes source code to detect naming conventions:
- Class naming: PascalCase, camelCase, snake_case
- Method naming: camelCase, snake_case, etc.
- File naming patterns
- Documentation style: PHPDoc, JSDoc, docstrings
"""

import re
from pathlib import Path
from collections import Counter
from typing import Optional

from process_os.architecture import ProgrammingLanguage
from process_os.conventions.types import NamingStyle


class NamingAnalyzer:
    """Analyzes naming conventions in source code.

    Detects and analyzes:
    - Class naming patterns (PascalCase, camelCase, etc.)
    - Method naming patterns
    - File naming patterns
    - Documentation styles
    """

    # Regex patterns for detecting naming styles
    PASCAL_CASE_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
    CAMEL_CASE_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
    SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    KEBAB_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
    SCREAMING_SNAKE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

    def __init__(self):
        """Initialize the naming analyzer."""
        pass

    def analyze_class_names(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> Optional[NamingStyle]:
        """Analyze class naming patterns in files.

        Args:
            file_paths: List of source files to analyze
            language: Programming language

        Returns:
            Detected NamingStyle or None
        """
        class_names = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            names = self._extract_class_names(file_path, language)
            class_names.extend(names)

        if not class_names:
            return None

        return self._detect_dominant_style(class_names)

    def analyze_method_names(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> Optional[NamingStyle]:
        """Analyze method naming patterns in files.

        Args:
            file_paths: List of source files to analyze
            language: Programming language

        Returns:
            Detected NamingStyle or None
        """
        method_names = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            names = self._extract_method_names(file_path, language)
            method_names.extend(names)

        if not method_names:
            return None

        return self._detect_dominant_style(method_names)

    def analyze_file_names(self, file_paths: list[Path]) -> Optional[NamingStyle]:
        """Analyze file naming patterns.

        Args:
            file_paths: List of source files to analyze

        Returns:
            Detected NamingStyle or None
        """
        file_names = []

        for file_path in file_paths:
            # Get stem without extension
            stem = file_path.stem
            file_names.append(stem)

        if not file_names:
            return None

        return self._detect_dominant_style(file_names)

    def analyze_documentation_style(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> Optional[str]:
        """Analyze documentation style used in code.

        Args:
            file_paths: List of source files to analyze
            language: Programming language

        Returns:
            Documentation style string (e.g., "PHPDoc", "JSDoc", "docstring")
        """
        doc_styles = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue

            # Detect PHPDoc style
            if language == ProgrammingLanguage.PHP:
                if "/**" in content:
                    doc_styles.append("PHPDoc")
                elif "/*" in content:
                    doc_styles.append("MultilineComment")
                elif "//" in content:
                    doc_styles.append("SinglelineComment")

            # Detect JSDoc style
            elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
                if "/**" in content:
                    doc_styles.append("JSDoc")
                elif "/*" in content:
                    doc_styles.append("MultilineComment")
                elif "//" in content:
                    doc_styles.append("SinglelineComment")

            # Detect Python docstring style
            elif language == ProgrammingLanguage.PYTHON:
                if '"""' in content:
                    doc_styles.append("Docstring")
                elif "'''" in content:
                    doc_styles.append("Docstring")
                elif "#" in content:
                    doc_styles.append("Comment")

        if not doc_styles:
            return None

        # Return most common style
        counter = Counter(doc_styles)
        return counter.most_common(1)[0][0]

    def _extract_class_names(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> list[str]:
        """Extract class names from a file.

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            List of class names found
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return []

        class_names = []

        if language == ProgrammingLanguage.PHP:
            # Match PHP class declarations
            pattern = re.compile(r"class\s+(\w+)")
            matches = pattern.findall(content)
            class_names.extend(matches)

            # Match PHP interface declarations
            pattern = re.compile(r"interface\s+(\w+)")
            matches = pattern.findall(content)
            class_names.extend(matches)

        elif language == ProgrammingLanguage.PYTHON:
            # Match Python class declarations
            pattern = re.compile(r"^class\s+(\w+)", re.MULTILINE)
            matches = pattern.findall(content)
            class_names.extend(matches)

        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            # Match JavaScript/TypeScript class declarations
            pattern = re.compile(r"(?:export\s+)?class\s+(\w+)")
            matches = pattern.findall(content)
            class_names.extend(matches)

        return class_names

    def _extract_method_names(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> list[str]:
        """Extract method names from a file.

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            List of method names found
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return []

        method_names = []

        if language == ProgrammingLanguage.PHP:
            # Match PHP method declarations
            pattern = re.compile(r"(?:public|protected|private)?\s*function\s+(\w+)")
            matches = pattern.findall(content)
            # Filter out magic methods and constructors
            method_names.extend([m for m in matches if not m.startswith("__")])

        elif language == ProgrammingLanguage.PYTHON:
            # Match Python method declarations
            pattern = re.compile(r"^\s+def\s+(\w+)", re.MULTILINE)
            matches = pattern.findall(content)
            # Filter out magic methods and private methods for cleaner detection
            method_names.extend([m for m in matches if not m.startswith("_")])

        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            # Match JavaScript/TypeScript method declarations
            pattern = re.compile(r"(\w+)\s*\(")
            matches = pattern.findall(content)
            # Filter out constructor calls
            method_names.extend([m for m in matches if m.lower() not in ["new"]])

        return method_names

    def _detect_dominant_style(self, names: list[str]) -> Optional[NamingStyle]:
        """Detect the dominant naming style from a list of names.

        Args:
            names: List of names to analyze

        Returns:
            Detected NamingStyle or None
        """
        if not names:
            return None

        # Count matches for each style
        style_counts = {
            NamingStyle.PASCAL_CASE: 0,
            NamingStyle.CAMEL_CASE: 0,
            NamingStyle.SNAKE_CASE: 0,
            NamingStyle.KEBAB_CASE: 0,
            NamingStyle.SCREAMING_SNAKE: 0,
        }

        for name in names:
            # Try each pattern
            if self.PASCAL_CASE_PATTERN.match(name):
                style_counts[NamingStyle.PASCAL_CASE] += 1
            elif self.CAMEL_CASE_PATTERN.match(name):
                style_counts[NamingStyle.CAMEL_CASE] += 1
            elif self.SCREAMING_SNAKE_PATTERN.match(name):
                style_counts[NamingStyle.SCREAMING_SNAKE] += 1
            elif self.SNAKE_CASE_PATTERN.match(name):
                style_counts[NamingStyle.SNAKE_CASE] += 1
            elif self.KEBAB_CASE_PATTERN.match(name):
                style_counts[NamingStyle.KEBAB_CASE] += 1

        # Return style with highest count
        if not any(style_counts.values()):
            return None

        return max(style_counts, key=style_counts.get)
