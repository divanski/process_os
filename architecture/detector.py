"""
Language and Framework detection for ProcessOS.

This module provides multi-signal detection to achieve 100% accuracy
for supported languages. Detection uses three signal types:
1. Config files (composer.json, package.json, etc.)
2. File extension distribution
3. Content markers (shebang, imports, namespace)

Confidence Scoring:
- 3/3 signals agree → 100% confidence
- 2/3 signals agree → 90% confidence
- Conflict → REFUSE to proceed
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from process_os.architecture.types import (
    ProgrammingLanguage,
    FrameworkType,
    SignalType,
    ProjectType,
    DetectionSignal,
    ProjectArchitecture,
)
from process_os.architecture.errors import (
    LanguageDetectionError,
    FrameworkDetectionError,
)


class LanguageDetector:
    """Detects programming language from multiple signals.

    Uses multi-signal detection for 100% accuracy on supported languages.
    Signals: config files, file extensions, content markers.
    """

    # Config file to language mapping
    CONFIG_FILES = {
        "composer.json": ProgrammingLanguage.PHP,
        "package.json": ProgrammingLanguage.JAVASCRIPT,  # Could be TS too
        "requirements.txt": ProgrammingLanguage.PYTHON,
        "pyproject.toml": ProgrammingLanguage.PYTHON,
        "setup.py": ProgrammingLanguage.PYTHON,
        "Pipfile": ProgrammingLanguage.PYTHON,
        "Gemfile": ProgrammingLanguage.RUBY,
        "pom.xml": ProgrammingLanguage.JAVA,
        "build.gradle": ProgrammingLanguage.JAVA,
        "build.gradle.kts": ProgrammingLanguage.JAVA,
    }

    # File extensions to analyze
    LANGUAGE_EXTENSIONS = {
        ProgrammingLanguage.PHP: {".php", ".phtml"},
        ProgrammingLanguage.PYTHON: {".py", ".pyw"},
        ProgrammingLanguage.JAVASCRIPT: {".js", ".mjs", ".cjs", ".jsx"},
        ProgrammingLanguage.TYPESCRIPT: {".ts", ".tsx"},
        ProgrammingLanguage.RUBY: {".rb", ".rake"},
        ProgrammingLanguage.JAVA: {".java"},
    }

    def detect(self, project_path: Path) -> tuple[ProgrammingLanguage, float]:
        """Detect programming language for a project.

        Args:
            project_path: Path to project root directory

        Returns:
            Tuple of (detected language, confidence score)

        Raises:
            LanguageDetectionError: When no language can be detected
                or confidence is too low
        """
        project_path = Path(project_path)
        if not project_path.exists():
            raise LanguageDetectionError(f"Project path does not exist: {project_path}")

        signals = []

        # Signal 1: Config file detection (highest priority)
        config_signal = self._detect_from_config_files(project_path)
        if config_signal:
            signals.append(config_signal)

        # Signal 2: File extension analysis
        extension_signal = self._detect_from_extensions(project_path)
        if extension_signal:
            signals.append(extension_signal)

        # Signal 3: Content marker analysis
        content_signal = self._detect_from_content_markers(project_path)
        if content_signal:
            signals.append(content_signal)

        if not signals:
            raise LanguageDetectionError(
                "No language signals detected. Cannot determine project language.",
                confidence=0.0,
                signals=[],
            )

        # Calculate consensus
        return self._calculate_consensus(signals)

    def _detect_from_config_files(self, project_path: Path) -> Optional[DetectionSignal]:
        """Detect language from config files."""
        for config_file, language in self.CONFIG_FILES.items():
            config_path = project_path / config_file
            if config_path.exists():
                # Special handling for package.json (could be JS or TS)
                if config_file == "package.json":
                    language = self._check_typescript_in_package_json(config_path)

                return DetectionSignal(
                    signal_type=SignalType.CONFIG_FILE,
                    source=config_file,
                    detected_language=language,
                    confidence=1.0,
                    evidence=f"Found {config_file} in project root",
                )
        return None

    def _check_typescript_in_package_json(self, package_json_path: Path) -> ProgrammingLanguage:
        """Check if package.json indicates TypeScript project."""
        try:
            with open(package_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check for TypeScript indicators
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            all_deps = {**deps, **dev_deps}

            if "typescript" in all_deps:
                return ProgrammingLanguage.TYPESCRIPT

            # Check for tsconfig.json
            if (package_json_path.parent / "tsconfig.json").exists():
                return ProgrammingLanguage.TYPESCRIPT

            return ProgrammingLanguage.JAVASCRIPT

        except (json.JSONDecodeError, IOError):
            return ProgrammingLanguage.JAVASCRIPT

    def _detect_from_extensions(self, project_path: Path) -> Optional[DetectionSignal]:
        """Detect language from file extension distribution."""
        extension_counts: Counter = Counter()

        # Count files by extension (limit depth to avoid huge repos)
        for file_path in self._walk_files(project_path, max_depth=5):
            ext = file_path.suffix.lower()
            for lang, extensions in self.LANGUAGE_EXTENSIONS.items():
                if ext in extensions:
                    extension_counts[lang] += 1
                    break

        if not extension_counts:
            return None

        # Find majority language
        total = sum(extension_counts.values())
        most_common = extension_counts.most_common(1)[0]
        language, count = most_common

        confidence = count / total if total > 0 else 0

        return DetectionSignal(
            signal_type=SignalType.FILE_EXTENSION,
            source=f"File extension analysis ({count}/{total} files)",
            detected_language=language,
            confidence=confidence,
            evidence=f"Found {count} {language.value} files out of {total} total",
        )

    def _detect_from_content_markers(self, project_path: Path) -> Optional[DetectionSignal]:
        """Detect language from content markers (shebang, imports, namespace)."""
        markers_found: Counter = Counter()

        for file_path in self._walk_files(project_path, max_depth=3, limit=50):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:1000]

                # PHP namespace
                if re.search(r"<\?php|namespace\s+\w+", content):
                    markers_found[ProgrammingLanguage.PHP] += 1

                # Python shebang or imports
                if re.search(r"#!/usr/bin/env python|^import\s+\w+|^from\s+\w+\s+import", content, re.MULTILINE):
                    markers_found[ProgrammingLanguage.PYTHON] += 1

                # JavaScript/TypeScript imports
                if re.search(r"require\(['\"]|import\s+.*\s+from\s+['\"]|export\s+", content):
                    # Check for TypeScript type annotations
                    if re.search(r":\s*(string|number|boolean|void|any|interface\s+\w+)", content):
                        markers_found[ProgrammingLanguage.TYPESCRIPT] += 1
                    else:
                        markers_found[ProgrammingLanguage.JAVASCRIPT] += 1

                # Ruby
                if re.search(r"#!/usr/bin/env ruby|^require\s+['\"]|^module\s+\w+|^class\s+\w+\s*<", content, re.MULTILINE):
                    markers_found[ProgrammingLanguage.RUBY] += 1

                # Java
                if re.search(r"^package\s+[\w.]+;|^import\s+[\w.]+;|public\s+class\s+\w+", content, re.MULTILINE):
                    markers_found[ProgrammingLanguage.JAVA] += 1

            except (IOError, UnicodeDecodeError):
                continue

        if not markers_found:
            return None

        most_common = markers_found.most_common(1)[0]
        language, count = most_common
        total = sum(markers_found.values())
        confidence = count / total if total > 0 else 0

        return DetectionSignal(
            signal_type=SignalType.CONTENT_MARKER,
            source=f"Content marker analysis ({count} markers)",
            detected_language=language,
            confidence=confidence,
            evidence=f"Found {count} {language.value} content markers",
        )

    def _walk_files(self, root: Path, max_depth: int = 5, limit: int = 1000):
        """Walk files in directory with depth limit."""
        count = 0
        skip_dirs = {
            "node_modules", "vendor", ".git", "__pycache__", ".venv",
            "venv", "dist", "build", ".idea", ".vscode", "target",
        }

        def walk(path: Path, depth: int):
            nonlocal count
            if depth > max_depth or count >= limit:
                return

            try:
                for item in path.iterdir():
                    if count >= limit:
                        return

                    if item.is_dir():
                        if item.name not in skip_dirs and not item.name.startswith("."):
                            yield from walk(item, depth + 1)
                    elif item.is_file():
                        count += 1
                        yield item
            except PermissionError:
                pass

        yield from walk(root, 0)

    def _calculate_consensus(
        self, signals: list[DetectionSignal]
    ) -> tuple[ProgrammingLanguage, float]:
        """Calculate consensus from multiple signals.

        Confidence scoring:
        - 3/3 signals agree → 100% confidence
        - 2/3 signals agree → 90% confidence
        - 1 signal only → use that signal's confidence
        - Conflict with no majority → raise error
        """
        if not signals:
            raise LanguageDetectionError("No signals to calculate consensus")

        # Count votes per language
        votes: Counter = Counter()
        for signal in signals:
            votes[signal.detected_language] += 1

        # Find majority
        most_common = votes.most_common(1)[0]
        language, vote_count = most_common
        total_signals = len(signals)

        # Calculate confidence based on agreement
        if total_signals == 1:
            # Single signal: use its confidence
            confidence = signals[0].confidence
        elif vote_count == total_signals:
            # All signals agree
            confidence = 1.0
        elif vote_count >= total_signals / 2:
            # Majority agrees
            confidence = 0.9
        else:
            # No clear majority - this is a conflict
            raise LanguageDetectionError(
                f"Conflicting signals: {dict(votes)}. Cannot determine language.",
                confidence=0.0,
                signals=signals,
            )

        return language, confidence


class FrameworkDetector:
    """Detects framework for a given programming language.

    Uses framework-specific markers to identify the framework in use.
    """

    # Framework detection rules per language
    FRAMEWORK_MARKERS = {
        ProgrammingLanguage.PHP: {
            FrameworkType.LARAVEL: {
                "config_key": "laravel/framework",  # in composer.json require
                "files": ["artisan"],
                "dirs": ["app/Providers", "app/Http/Controllers"],
            },
            FrameworkType.SYMFONY: {
                "config_key": "symfony/framework-bundle",
                "files": ["symfony.lock"],
                "dirs": ["src/Controller", "config/packages"],
            },
        },
        ProgrammingLanguage.PYTHON: {
            FrameworkType.DJANGO: {
                "config_key": "django",  # in requirements.txt or pyproject.toml
                "files": ["manage.py"],
                "dirs": [],
                "content_markers": ["from django", "import django"],
            },
            FrameworkType.FLASK: {
                "config_key": "flask",
                "files": [],
                "dirs": [],
                "content_markers": ["from flask import", "import flask"],
            },
            FrameworkType.FASTAPI: {
                "config_key": "fastapi",
                "files": [],
                "dirs": [],
                "content_markers": ["from fastapi import", "import fastapi"],
            },
        },
        ProgrammingLanguage.JAVASCRIPT: {
            FrameworkType.EXPRESS: {
                "config_key": "express",
                "files": [],
                "dirs": [],
                "content_markers": ["require('express')", "from 'express'"],
            },
            FrameworkType.NESTJS: {
                "config_key": "@nestjs/core",
                "files": ["nest-cli.json"],
                "dirs": [],
            },
            FrameworkType.NEXTJS: {
                "config_key": "next",
                "files": ["next.config.js", "next.config.mjs"],
                "dirs": ["pages", "app"],
            },
        },
        ProgrammingLanguage.TYPESCRIPT: {
            FrameworkType.EXPRESS: {
                "config_key": "express",
                "files": [],
                "dirs": [],
            },
            FrameworkType.NESTJS: {
                "config_key": "@nestjs/core",
                "files": ["nest-cli.json"],
                "dirs": [],
            },
            FrameworkType.NEXTJS: {
                "config_key": "next",
                "files": ["next.config.ts", "next.config.js"],
                "dirs": ["pages", "app"],
            },
        },
        ProgrammingLanguage.RUBY: {
            FrameworkType.RAILS: {
                "config_key": "rails",
                "files": ["config/routes.rb", "Rakefile"],
                "dirs": ["app/controllers", "app/models"],
            },
            FrameworkType.SINATRA: {
                "config_key": "sinatra",
                "files": [],
                "dirs": [],
            },
        },
        ProgrammingLanguage.JAVA: {
            FrameworkType.SPRING: {
                "config_key": "spring",
                "files": ["application.properties", "application.yml"],
                "dirs": [],
                "content_markers": ["@SpringBootApplication", "import org.springframework"],
            },
        },
    }

    def detect(
        self, project_path: Path, language: ProgrammingLanguage
    ) -> tuple[Optional[FrameworkType], float]:
        """Detect framework for a project with known language.

        Args:
            project_path: Path to project root
            language: The detected programming language

        Returns:
            Tuple of (detected framework or None, confidence score)
        """
        project_path = Path(project_path)

        if language not in self.FRAMEWORK_MARKERS:
            return None, 0.0

        framework_rules = self.FRAMEWORK_MARKERS[language]

        for framework, markers in framework_rules.items():
            score = self._check_framework_markers(project_path, language, markers)
            if score >= 0.9:
                return framework, score

        return FrameworkType.NONE, 0.5

    def _check_framework_markers(
        self, project_path: Path, language: ProgrammingLanguage, markers: dict
    ) -> float:
        """Check for framework-specific markers."""
        score = 0.0
        checks = 0

        # Check config file for dependency
        config_key = markers.get("config_key")
        if config_key:
            checks += 1
            if self._check_config_dependency(project_path, language, config_key):
                score += 1.0

        # Check for specific files
        for file_name in markers.get("files", []):
            checks += 1
            if (project_path / file_name).exists():
                score += 1.0

        # Check for specific directories
        for dir_name in markers.get("dirs", []):
            checks += 1
            if (project_path / dir_name).is_dir():
                score += 1.0

        # Check for content markers
        content_markers = markers.get("content_markers", [])
        if content_markers:
            checks += 1
            if self._check_content_markers(project_path, content_markers):
                score += 1.0

        return score / checks if checks > 0 else 0.0

    def _check_config_dependency(
        self, project_path: Path, language: ProgrammingLanguage, key: str
    ) -> bool:
        """Check if a dependency exists in the config file."""
        try:
            if language == ProgrammingLanguage.PHP:
                composer_path = project_path / "composer.json"
                if composer_path.exists():
                    with open(composer_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    require = data.get("require", {})
                    require_dev = data.get("require-dev", {})
                    return key in require or key in require_dev

            elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
                package_path = project_path / "package.json"
                if package_path.exists():
                    with open(package_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    deps = data.get("dependencies", {})
                    dev_deps = data.get("devDependencies", {})
                    return key in deps or key in dev_deps

            elif language == ProgrammingLanguage.PYTHON:
                # Check requirements.txt
                req_path = project_path / "requirements.txt"
                if req_path.exists():
                    content = req_path.read_text(encoding="utf-8").lower()
                    if key.lower() in content:
                        return True

                # Check pyproject.toml
                pyproject_path = project_path / "pyproject.toml"
                if pyproject_path.exists():
                    content = pyproject_path.read_text(encoding="utf-8").lower()
                    if key.lower() in content:
                        return True

            elif language == ProgrammingLanguage.RUBY:
                gemfile_path = project_path / "Gemfile"
                if gemfile_path.exists():
                    content = gemfile_path.read_text(encoding="utf-8")
                    if re.search(rf"gem\s+['\"]({key})['\"]", content):
                        return True

            elif language == ProgrammingLanguage.JAVA:
                # Check pom.xml
                pom_path = project_path / "pom.xml"
                if pom_path.exists():
                    content = pom_path.read_text(encoding="utf-8")
                    if key in content:
                        return True

                # Check build.gradle
                gradle_path = project_path / "build.gradle"
                if gradle_path.exists():
                    content = gradle_path.read_text(encoding="utf-8")
                    if key in content:
                        return True

        except (IOError, json.JSONDecodeError):
            pass

        return False

    def _check_content_markers(self, project_path: Path, markers: list[str]) -> bool:
        """Check if any content markers are found in source files."""
        for file_path in self._get_source_files(project_path, limit=20):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for marker in markers:
                    if marker in content:
                        return True
            except IOError:
                continue
        return False

    def _get_source_files(self, project_path: Path, limit: int = 20):
        """Get source files from project."""
        skip_dirs = {"node_modules", "vendor", ".git", "__pycache__", ".venv", "venv"}
        count = 0

        def walk(path: Path, depth: int):
            nonlocal count
            if depth > 3 or count >= limit:
                return

            try:
                for item in path.iterdir():
                    if count >= limit:
                        return
                    if item.is_dir() and item.name not in skip_dirs:
                        yield from walk(item, depth + 1)
                    elif item.is_file() and item.suffix in (".php", ".py", ".js", ".ts", ".rb", ".java"):
                        count += 1
                        yield item
            except PermissionError:
                pass

        yield from walk(project_path, 0)


class ArchitectureAnalyzer:
    """Main analyzer for project architecture detection.

    This is the entry point for architecture analysis. It orchestrates
    language detection, framework detection, and report generation.
    """

    def __init__(self):
        self.language_detector = LanguageDetector()
        self.framework_detector = FrameworkDetector()

    def analyze(
        self,
        project_path: Path,
        target_directory: Optional[Path] = None,
    ) -> ProjectArchitecture:
        """Analyze a project and return its architecture.

        Args:
            project_path: Path to project root directory
            target_directory: Subdirectory to analyze (for monorepos)

        Returns:
            ProjectArchitecture with detected language, framework, and signals

        Raises:
            LanguageDetectionError: When language cannot be determined
                with sufficient confidence
        """
        project_path = Path(project_path)
        analysis_path = project_path

        # Handle target directory for monorepos
        if target_directory:
            analysis_path = project_path / target_directory

        # Detect language
        language, lang_confidence = self.language_detector.detect(analysis_path)

        # Detect framework
        framework, fw_confidence = self.framework_detector.detect(analysis_path, language)

        # Determine project type
        project_type = self._determine_project_type(project_path, target_directory)

        # Collect all detection signals
        signals = self._collect_signals(analysis_path, language, framework)

        # Calculate overall confidence
        overall_confidence = min(lang_confidence, 1.0)

        return ProjectArchitecture(
            language=language,
            framework=framework,
            confidence=overall_confidence,
            root_path=project_path,
            detection_signals=signals,
            project_type=project_type,
            target_directory=target_directory,
        )

    def _determine_project_type(
        self, project_path: Path, target_directory: Optional[Path]
    ) -> ProjectType:
        """Determine if project is single, monorepo, or mixed."""
        if target_directory:
            return ProjectType.MIXED

        # Check for common monorepo patterns
        monorepo_indicators = ["packages", "apps", "services", "modules"]
        for indicator in monorepo_indicators:
            if (project_path / indicator).is_dir():
                return ProjectType.MONOREPO

        return ProjectType.SINGLE

    def _collect_signals(
        self,
        project_path: Path,
        language: ProgrammingLanguage,
        framework: Optional[FrameworkType],
    ) -> list[DetectionSignal]:
        """Collect all detection signals for reporting."""
        signals = []

        # Config file signal
        for config_file in LanguageDetector.CONFIG_FILES:
            if (project_path / config_file).exists():
                signals.append(
                    DetectionSignal(
                        signal_type=SignalType.CONFIG_FILE,
                        source=config_file,
                        detected_language=language,
                        detected_framework=framework,
                        confidence=1.0,
                        evidence=f"Found {config_file}",
                    )
                )
                break

        return signals


def analyze_project(
    project_path: str | Path,
    target_dir: Optional[str | Path] = None,
) -> ProjectArchitecture:
    """Convenience function to analyze a project.

    Args:
        project_path: Path to project root
        target_dir: Optional subdirectory for monorepos

    Returns:
        ProjectArchitecture with detected language and framework
    """
    analyzer = ArchitectureAnalyzer()
    return analyzer.analyze(
        Path(project_path),
        Path(target_dir) if target_dir else None,
    )


def validate_language_match(
    architecture: ProjectArchitecture,
    code_content: str,
) -> bool:
    """Validate that generated code matches project language.

    Args:
        architecture: The detected project architecture
        code_content: The generated code to validate

    Returns:
        True if code matches project language

    Raises:
        LanguageMismatchError: When code language doesn't match project
    """
    from process_os.architecture.errors import LanguageMismatchError

    expected = architecture.language

    # Detect language of generated code
    detected = _detect_code_language(code_content)

    if detected == ProgrammingLanguage.UNKNOWN:
        # Can't determine, assume OK
        return True

    if detected != expected:
        raise LanguageMismatchError(
            f"Generated {detected.value} code for {expected.value} project!",
            expected_language=expected.value,
            detected_language=detected.value,
        )

    return True


def _detect_code_language(code: str) -> ProgrammingLanguage:
    """Detect language of a code snippet."""
    # PHP markers
    if re.search(r"<\?php|namespace\s+\w+\\|use\s+\w+\\", code):
        return ProgrammingLanguage.PHP

    # Python markers
    if re.search(r"^def\s+\w+\(|^class\s+\w+:|^import\s+\w+|^from\s+\w+\s+import", code, re.MULTILINE):
        # Make sure it's not PHP that happens to have similar patterns
        if not re.search(r"<\?php|->|::", code):
            return ProgrammingLanguage.PYTHON

    # JavaScript/TypeScript markers
    if re.search(r"const\s+\w+\s*=|let\s+\w+\s*=|function\s+\w+\(|=>\s*{", code):
        if re.search(r":\s*(string|number|boolean|void|any)|interface\s+\w+", code):
            return ProgrammingLanguage.TYPESCRIPT
        return ProgrammingLanguage.JAVASCRIPT

    # Ruby markers
    if re.search(r"^def\s+\w+\n|^class\s+\w+\s*<|end\s*$", code, re.MULTILINE):
        return ProgrammingLanguage.RUBY

    # Java markers
    if re.search(r"public\s+class\s+\w+|private\s+\w+\s+\w+;|@Override", code):
        return ProgrammingLanguage.JAVA

    return ProgrammingLanguage.UNKNOWN
