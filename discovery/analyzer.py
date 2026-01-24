"""
ProcessOS Discovery Analyzer Module

Orchestrates project structure discovery using framework-specific patterns.
Integrates with stack_fingerprint for language/framework detection.
"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from .context import (
    DiscoveryConfig,
    ExistingIntegration,
    LocalModel,
    ProjectContext,
    ProjectConventions,
    Route,
    Service,
)
from .patterns import (
    FrameworkPatterns,
    get_patterns_for_framework,
    infer_conventions,
)


class ProjectAnalyzer:
    """
    Analyzes project structure to build a comprehensive ProjectContext.

    Detects models, routes, services, and coding conventions
    across multiple frameworks (Django, Express, Laravel).
    """

    # Supported file extensions by language
    LANGUAGE_EXTENSIONS = {
        "python": [".py"],
        "javascript": [".js", ".mjs", ".cjs"],
        "typescript": [".ts", ".tsx"],
        "php": [".php"],
        "ruby": [".rb"],
        "java": [".java"],
    }

    # Framework detection patterns
    FRAMEWORK_INDICATORS = {
        "django": {
            "files": ["manage.py", "settings.py", "wsgi.py"],
            "imports": ["from django", "import django"],
            "dependencies": ["django"],
        },
        "express": {
            "files": ["package.json"],
            "imports": ["require('express')", "from 'express'", 'require("express")'],
            "dependencies": ["express"],
        },
        "laravel": {
            "files": ["artisan", "composer.json"],
            "imports": ["use Illuminate\\", "namespace App\\"],
            "dependencies": ["laravel/framework"],
        },
        "fastapi": {
            "files": [],
            "imports": ["from fastapi", "import fastapi"],
            "dependencies": ["fastapi"],
        },
        "flask": {
            "files": [],
            "imports": ["from flask", "import flask"],
            "dependencies": ["flask"],
        },
    }

    def __init__(
        self,
        project_root: str | Path,
        target_dir: Optional[str | Path] = None,
        config: Optional[DiscoveryConfig] = None,
        on_conflict: Optional[Callable[[str, List[str]], str]] = None,
    ):
        """
        Initialize the project analyzer.

        Args:
            project_root: Path to project root directory
            target_dir: Optional subdirectory to limit discovery scope
            config: Optional discovery configuration
            on_conflict: Callback for resolving conflicting pattern detections
        """
        self.root_path = Path(project_root).resolve()
        self.target_dir = Path(target_dir) if target_dir else None

        self.config = config or DiscoveryConfig(root_path=self.root_path)
        if target_dir:
            self.config.target_subdirectory = self.target_dir

        self.on_conflict = on_conflict

        # Discovery results
        self._models: List[LocalModel] = []
        self._routes: List[Route] = []
        self._services: List[Service] = []
        self._integrations: List[ExistingIntegration] = []
        self._conventions: Optional[ProjectConventions] = None

        # Detected framework and language
        self._language: Optional[str] = None
        self._framework: Optional[str] = None
        self._patterns: Optional[FrameworkPatterns] = None

        # File analysis stats
        self._file_count = 0
        self._analyzed_files: Set[Path] = set()
        self._code_samples: List[str] = []

    def analyze(self) -> ProjectContext:
        """
        Perform full project discovery.

        Returns:
            ProjectContext with discovered structure

        Raises:
            ProjectTooLargeError: If project exceeds file limit
            DiscoveryError: If discovery fails
        """
        from . import DiscoveryError, ProjectTooLargeError

        start_time = time.time()

        # Determine analysis scope
        analysis_root = self.root_path
        if self.target_dir:
            analysis_root = self.root_path / self.target_dir
            if not analysis_root.exists():
                raise DiscoveryError(f"Target directory does not exist: {self.target_dir}")

        # Count files first
        self._file_count = self._count_source_files(analysis_root)
        if self._file_count > self.config.max_file_count:
            raise ProjectTooLargeError(self._file_count, self.config.max_file_count)

        # Detect language and framework
        self._detect_stack(analysis_root)

        # Get appropriate pattern detector
        if self._framework:
            self._patterns = get_patterns_for_framework(self._framework)

        # Analyze models, routes, services
        if self.config.detect_models:
            self._models = self.analyze_models(analysis_root)

        if self.config.detect_routes:
            self._routes = self.analyze_routes(analysis_root)

        if self.config.detect_services:
            self._services = self.analyze_services(analysis_root)

        if self.config.detect_integrations:
            self._integrations = self._detect_integrations(analysis_root)

        # Infer conventions
        self._conventions = self.detect_conventions()

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Calculate confidence score
        confidence = self._calculate_confidence()

        # Build and return context
        context = ProjectContext(
            project_id=self._generate_project_id(),
            root_path=self.root_path,
            discovered_at=datetime.now(),
            language=self._language or "",
            framework=self._framework,
            models=self._models,
            routes=self._routes,
            services=self._services,
            existing_integrations=self._integrations,
            conventions=self._conventions,
            file_count=self._file_count,
            analysis_duration_ms=duration_ms,
            confidence_score=confidence,
        )

        return context

    def analyze_models(self, root: Path) -> List[LocalModel]:
        """
        Analyze and detect model definitions.

        Args:
            root: Directory to analyze

        Returns:
            List of discovered LocalModel objects
        """
        models = []

        if not self._patterns:
            return models

        # Find model files
        model_patterns = self._get_model_file_patterns()

        for file_path in self._iter_source_files(root, model_patterns):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                detected = self._patterns.detect_models(content, file_path.relative_to(self.root_path))
                models.extend(detected)
                self._code_samples.append(content[:2000])
            except Exception:
                continue  # Skip files that can't be read

        return models

    def analyze_routes(self, root: Path) -> List[Route]:
        """
        Analyze and detect route/endpoint definitions.

        Args:
            root: Directory to analyze

        Returns:
            List of discovered Route objects
        """
        routes = []

        if not self._patterns:
            return routes

        # Find route files
        route_patterns = self._get_route_file_patterns()

        for file_path in self._iter_source_files(root, route_patterns):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                detected = self._patterns.detect_routes(content, file_path.relative_to(self.root_path))
                routes.extend(detected)
            except Exception:
                continue

        return routes

    def analyze_services(self, root: Path) -> List[Service]:
        """
        Analyze and detect service class definitions.

        Args:
            root: Directory to analyze

        Returns:
            List of discovered Service objects
        """
        services = []

        if not self._patterns:
            return services

        # Find service files
        service_patterns = self._get_service_file_patterns()

        for file_path in self._iter_source_files(root, service_patterns):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                detected = self._patterns.detect_services(content, file_path.relative_to(self.root_path))
                services.extend(detected)
                self._code_samples.append(content[:2000])
            except Exception:
                continue

        return services

    def detect_conventions(self) -> ProjectConventions:
        """
        Detect coding conventions from analyzed code.

        Returns:
            ProjectConventions with detected patterns
        """
        if not self._code_samples:
            return ProjectConventions()

        # Combine code samples for analysis
        combined_code = "\n\n".join(self._code_samples[:10])  # Limit samples

        return infer_conventions(combined_code, self._language or "python")

    def _detect_stack(self, root: Path) -> None:
        """Detect language and framework from project files."""
        # Try to use existing stack_fingerprint if available
        try:
            from ..stack_fingerprint import detect_stack

            stack_info = detect_stack(str(root))
            if stack_info:
                self._language = stack_info.get("language")
                self._framework = stack_info.get("framework")
                return
        except ImportError:
            pass

        # Fallback to basic detection
        self._language = self._detect_language(root)
        self._framework = self._detect_framework(root)

    def _detect_language(self, root: Path) -> Optional[str]:
        """Detect primary programming language."""
        extension_counts: Dict[str, int] = {}

        for ext_list in self.LANGUAGE_EXTENSIONS.values():
            for ext in ext_list:
                extension_counts[ext] = 0

        for file_path in root.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in extension_counts:
                    extension_counts[ext] += 1

        # Find language with most files
        if not any(extension_counts.values()):
            return None

        max_ext = max(extension_counts, key=extension_counts.get)
        for language, extensions in self.LANGUAGE_EXTENSIONS.items():
            if max_ext in extensions:
                return language

        return None

    def _detect_framework(self, root: Path) -> Optional[str]:
        """Detect web framework from project indicators."""
        detected_frameworks = []

        for framework, indicators in self.FRAMEWORK_INDICATORS.items():
            score = 0

            # Check indicator files
            for indicator_file in indicators["files"]:
                if (root / indicator_file).exists():
                    score += 2

            # Check imports in source files
            for file_path in self._iter_source_files(root, ["**/*.py", "**/*.js", "**/*.php"]):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for import_pattern in indicators["imports"]:
                        if import_pattern in content:
                            score += 1
                            break
                except Exception:
                    continue

            # Check dependencies
            dep_file = self._get_dependency_file(root, framework)
            if dep_file and dep_file.exists():
                try:
                    content = dep_file.read_text()
                    for dep in indicators["dependencies"]:
                        if dep in content:
                            score += 3
                except Exception:
                    pass

            if score > 0:
                detected_frameworks.append((framework, score))

        if not detected_frameworks:
            return None

        # Handle conflicts
        if len(detected_frameworks) > 1 and self.on_conflict:
            frameworks = [f for f, _ in detected_frameworks]
            chosen = self.on_conflict("framework", frameworks)
            if chosen in frameworks:
                return chosen

        # Return highest scoring framework
        detected_frameworks.sort(key=lambda x: x[1], reverse=True)
        return detected_frameworks[0][0]

    def _get_dependency_file(self, root: Path, framework: str) -> Optional[Path]:
        """Get dependency file path for framework."""
        if framework in ("django", "flask", "fastapi"):
            for name in ["requirements.txt", "pyproject.toml", "setup.py"]:
                if (root / name).exists():
                    return root / name
        elif framework == "express":
            return root / "package.json"
        elif framework == "laravel":
            return root / "composer.json"
        return None

    def _detect_integrations(self, root: Path) -> List[ExistingIntegration]:
        """Detect existing external service integrations."""
        integrations: Dict[str, ExistingIntegration] = {}

        if not self._patterns:
            return []

        for file_path in self._iter_source_files(root):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                detected = self._patterns.detect_integrations(content, file_path.relative_to(self.root_path))

                for integration in detected:
                    key = integration.service_name
                    if key in integrations:
                        integrations[key].file_paths.append(file_path.relative_to(self.root_path))
                    else:
                        integrations[key] = integration
            except Exception:
                continue

        return list(integrations.values())

    def _count_source_files(self, root: Path) -> int:
        """Count source files in directory."""
        count = 0
        for file_path in self._iter_source_files(root):
            count += 1
        return count

    def _iter_source_files(
        self, root: Path, patterns: Optional[List[str]] = None
    ):
        """Iterate over source files matching patterns."""
        patterns = patterns or self.config.include_patterns

        for pattern in patterns:
            for file_path in root.glob(pattern):
                if file_path.is_file() and not self._should_exclude(file_path):
                    yield file_path

    def _should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        path_str = str(file_path)

        for exclude_pattern in self.config.exclude_patterns:
            # Simple pattern matching
            if "*" in exclude_pattern:
                pattern_parts = exclude_pattern.replace("**", ".*").replace("*", "[^/]*")
                import re
                if re.search(pattern_parts, path_str):
                    return True
            elif exclude_pattern in path_str:
                return True

        return False

    def _get_model_file_patterns(self) -> List[str]:
        """Get file patterns for model detection by framework."""
        patterns = {
            "django": ["**/models.py", "**/models/*.py"],
            "express": ["**/models/*.js", "**/models/*.ts", "**/schemas/*.js"],
            "laravel": ["**/Models/*.php", "**/Entities/*.php"],
        }
        return patterns.get(self._framework or "", ["**/*.py", "**/*.js", "**/*.php"])

    def _get_route_file_patterns(self) -> List[str]:
        """Get file patterns for route detection by framework."""
        patterns = {
            "django": ["**/urls.py", "**/routes.py"],
            "express": ["**/routes/*.js", "**/routes/*.ts", "**/routes.js"],
            "laravel": ["**/routes/*.php", "routes/api.php", "routes/web.php"],
        }
        return patterns.get(self._framework or "", ["**/urls.py", "**/routes*.py", "**/routes/*.js"])

    def _get_service_file_patterns(self) -> List[str]:
        """Get file patterns for service detection by framework."""
        patterns = {
            "django": ["**/services.py", "**/services/*.py"],
            "express": ["**/services/*.js", "**/services/*.ts"],
            "laravel": ["**/Services/*.php", "**/Repositories/*.php"],
        }
        return patterns.get(self._framework or "", ["**/services*.py", "**/services/*.js"])

    def _generate_project_id(self) -> str:
        """Generate unique project identifier."""
        path_hash = hashlib.sha256(str(self.root_path).encode()).hexdigest()[:12]
        return f"proj_{path_hash}"

    def _calculate_confidence(self) -> float:
        """Calculate discovery confidence score."""
        confidence = 0.0

        # Language detected
        if self._language:
            confidence += 0.2

        # Framework detected
        if self._framework:
            confidence += 0.2

        # Models found
        if self._models:
            confidence += 0.2

        # Routes found
        if self._routes:
            confidence += 0.2

        # Services found
        if self._services:
            confidence += 0.1

        # Conventions detected
        if self._conventions and self._conventions.service_pattern:
            confidence += 0.1

        return min(confidence, 1.0)

    def save_artifact(self, output_path: Optional[Path] = None) -> Path:
        """
        Save PROJECT_CONTEXT artifact to .processos directory.

        Args:
            output_path: Custom output path (default: .processos/PROJECT_CONTEXT.json)

        Returns:
            Path to saved artifact
        """
        if output_path is None:
            processos_dir = self.root_path / ".processos"
            processos_dir.mkdir(exist_ok=True)
            output_path = processos_dir / "PROJECT_CONTEXT.json"

        context = self.analyze()
        output_path.write_text(json.dumps(context.to_dict(), indent=2))
        return output_path

    @classmethod
    def load_cached(cls, project_root: str | Path) -> Optional[ProjectContext]:
        """
        Load cached ProjectContext if available and valid.

        Args:
            project_root: Path to project root

        Returns:
            Cached ProjectContext or None if not available/valid
        """
        root_path = Path(project_root).resolve()
        cache_path = root_path / ".processos" / "PROJECT_CONTEXT.json"

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())
            return ProjectContext.from_dict(data)
        except Exception:
            return None
