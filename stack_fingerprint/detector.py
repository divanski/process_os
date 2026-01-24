"""
ProcessOS Stack Detector

Evidence-based detection of technology stacks in a project.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .markers import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    FRAMEWORK_MARKERS,
    SKIP_DIRECTORIES,
    STACK_MARKERS,
    FrameworkMarker,
    StackMarker,
    get_framework_markers_for_stack,
)


@dataclass
class DetectedStack:
    """A detected technology stack."""

    stack_id: str
    confidence: str  # "high", "medium", "low"
    markers_found: List[str]
    version_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "stack_id": self.stack_id,
            "confidence": self.confidence,
            "markers_found": sorted(self.markers_found),
        }
        if self.version_hint:
            result["version_hint"] = self.version_hint
        return result


@dataclass
class DetectedFramework:
    """A detected framework."""

    framework_id: str
    stack: str
    confidence: str
    markers_found: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "framework_id": self.framework_id,
            "stack": self.stack,
            "confidence": self.confidence,
            "markers_found": sorted(self.markers_found),
        }


@dataclass
class DetectionResult:
    """Result of stack detection."""

    project_root: Path
    stacks: List[DetectedStack] = field(default_factory=list)
    frameworks: List[DetectedFramework] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_root": str(self.project_root),
            "stacks": [s.to_dict() for s in self.stacks],
            "frameworks": [f.to_dict() for f in self.frameworks],
        }


class StackDetector:
    """
    Detects technology stacks in a project directory.

    Uses evidence-based detection via file markers.
    """

    def __init__(self, max_depth: int = 2):
        """
        Initialize detector.

        Args:
            max_depth: Maximum directory depth to scan
        """
        self.max_depth = max_depth

    def detect(self, project_root: Path) -> DetectionResult:
        """
        Detect stacks in the given project.

        Args:
            project_root: Path to project root

        Returns:
            DetectionResult with detected stacks and frameworks
        """
        project_root = Path(project_root).resolve()

        if not project_root.is_dir():
            return DetectionResult(project_root=project_root)

        # Collect all files in scope
        files = self._collect_files(project_root)

        # Detect stacks
        stacks = self._detect_stacks(project_root, files)

        # Detect frameworks based on detected stacks
        frameworks = self._detect_frameworks(project_root, stacks)

        return DetectionResult(
            project_root=project_root,
            stacks=stacks,
            frameworks=frameworks,
        )

    def _collect_files(self, root: Path) -> List[Path]:
        """Collect files within max_depth, skipping excluded directories."""
        files: List[Path] = []

        def walk(path: Path, depth: int) -> None:
            if depth > self.max_depth:
                return

            try:
                for entry in path.iterdir():
                    if entry.is_file():
                        files.append(entry)
                    elif entry.is_dir():
                        if entry.name not in SKIP_DIRECTORIES:
                            walk(entry, depth + 1)
            except PermissionError:
                pass  # Skip unreadable directories

        walk(root, 0)
        return files

    def _detect_stacks(
        self, project_root: Path, files: List[Path]
    ) -> List[DetectedStack]:
        """Detect technology stacks based on marker files."""
        detected: List[DetectedStack] = []
        file_names = {f.name for f in files}
        relative_paths = {str(f.relative_to(project_root)) for f in files}

        for marker in STACK_MARKERS:
            found_markers = self._find_markers(
                marker.markers, file_names, relative_paths
            )

            if found_markers:
                # Determine confidence
                high_found = self._find_markers(
                    marker.high_confidence, file_names, relative_paths
                )
                if high_found:
                    confidence = "high"
                elif len(found_markers) >= 2:
                    confidence = "medium"
                else:
                    confidence = "low"

                # Extract version hint
                version_hint = self._extract_version(
                    project_root, marker, file_names
                )

                detected.append(
                    DetectedStack(
                        stack_id=marker.stack_id,
                        confidence=confidence,
                        markers_found=list(found_markers),
                        version_hint=version_hint,
                    )
                )

        return detected

    def _find_markers(
        self,
        patterns: List[str],
        file_names: set,
        relative_paths: set,
    ) -> set:
        """Find which marker patterns match any files."""
        found = set()

        for pattern in patterns:
            if "*" in pattern:
                # Glob pattern
                for name in file_names:
                    if fnmatch.fnmatch(name, pattern):
                        found.add(pattern)
                        break
            else:
                # Exact match
                if pattern in file_names or pattern in relative_paths:
                    found.add(pattern)

        return found

    def _extract_version(
        self,
        project_root: Path,
        marker: StackMarker,
        file_names: set,
    ) -> Optional[str]:
        """Try to extract version hint from version files."""
        for version_file in marker.version_files:
            if version_file in file_names:
                version_path = project_root / version_file
                if version_path.exists():
                    try:
                        content = version_path.read_text(encoding="utf-8")
                        return self._parse_version(marker.stack_id, version_file, content)
                    except (OSError, UnicodeDecodeError):
                        pass
        return None

    def _parse_version(
        self, stack_id: str, filename: str, content: str
    ) -> Optional[str]:
        """Parse version from file content."""
        if stack_id == "python":
            if filename == "pyproject.toml":
                match = re.search(r'python\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            elif filename == ".python-version":
                return content.strip().split("\n")[0].strip()

        elif stack_id == "node":
            if filename == ".nvmrc" or filename == ".node-version":
                return content.strip().split("\n")[0].strip()
            elif filename == "package.json":
                match = re.search(r'"node"\s*:\s*"([^"]+)"', content)
                if match:
                    return match.group(1)

        elif stack_id == "go":
            if filename == "go.mod":
                match = re.search(r"^go\s+(\d+\.\d+)", content, re.MULTILINE)
                if match:
                    return match.group(1)

        elif stack_id == "rust":
            if filename == "rust-toolchain.toml":
                match = re.search(r'channel\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)

        return None

    def _detect_frameworks(
        self,
        project_root: Path,
        stacks: List[DetectedStack],
    ) -> List[DetectedFramework]:
        """Detect frameworks based on dependencies and multi-signal confidence."""
        detected: List[DetectedFramework] = []
        stack_ids = {s.stack_id for s in stacks}

        # Collect files for enhanced detection
        files = self._collect_files(project_root)
        file_names = {f.name for f in files}
        relative_paths = {str(f.relative_to(project_root)) for f in files}

        for stack_id in stack_ids:
            framework_markers = get_framework_markers_for_stack(stack_id)
            if not framework_markers:
                continue

            # Read dependency files
            dependencies = self._read_dependencies(project_root, stack_id)

            for fm in framework_markers:
                found_deps = [
                    dep for dep in fm.dependency_names if dep in dependencies
                ]
                if found_deps:
                    # Use enhanced multi-signal confidence aggregation
                    confidence, markers_found = self._calculate_framework_confidence(
                        project_root, fm, file_names, relative_paths, found_deps
                    )
                    detected.append(
                        DetectedFramework(
                            framework_id=fm.framework_id,
                            stack=fm.stack,
                            confidence=confidence,
                            markers_found=markers_found,
                        )
                    )

        return detected

    def _calculate_framework_confidence(
        self,
        project_root: Path,
        marker: FrameworkMarker,
        file_names: set,
        relative_paths: set,
        found_deps: List[str],
    ) -> tuple:
        """
        Calculate confidence using multi-signal aggregation (T019).

        Returns:
            Tuple of (confidence_level, list of markers found)
        """
        markers_found = [f"{dep} in dependencies" for dep in found_deps]
        confidence_score = 0.0

        # Base score from dependency detection
        confidence_score += 0.4 if found_deps else 0.0

        # Check primary files
        if marker.primary_files:
            primary_found = self._find_markers(
                marker.primary_files, file_names, relative_paths
            )
            if primary_found:
                confidence_score += 0.3
                markers_found.extend([f"primary: {f}" for f in primary_found])

        # Check secondary files
        if marker.secondary_files:
            secondary_found = self._find_markers(
                marker.secondary_files, file_names, relative_paths
            )
            # Each secondary file adds to confidence (up to a cap)
            secondary_boost = min(
                len(secondary_found) * marker.confidence_boost, 0.3
            )
            confidence_score += secondary_boost
            if secondary_found:
                markers_found.extend([f"secondary: {f}" for f in secondary_found])

        # Check content patterns
        if marker.content_patterns:
            content_matches = self._check_content_patterns(
                project_root, marker.content_patterns, file_names
            )
            if content_matches:
                confidence_score += 0.2
                markers_found.extend([f"content: {f}" for f in content_matches])

        # Determine confidence level
        if confidence_score >= 0.7:
            confidence = CONFIDENCE_HIGH
        elif confidence_score >= 0.4:
            confidence = CONFIDENCE_MEDIUM
        else:
            confidence = CONFIDENCE_LOW

        return confidence, markers_found

    def _check_content_patterns(
        self,
        project_root: Path,
        patterns: Dict[str, str],
        file_names: set,
    ) -> List[str]:
        """Check content patterns against file contents."""
        matches = []

        for filename, pattern in patterns.items():
            if filename in file_names:
                file_path = project_root / filename
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        if re.search(pattern, content):
                            matches.append(filename)
                    except (OSError, UnicodeDecodeError):
                        pass

        return matches

    def _read_dependencies(
        self, project_root: Path, stack_id: str
    ) -> set:
        """Read dependency names for a stack."""
        dependencies: set = set()

        if stack_id == "python":
            # Check pyproject.toml
            pyproject = project_root / "pyproject.toml"
            if pyproject.exists():
                try:
                    content = pyproject.read_text(encoding="utf-8")
                    # Extract package names, handling version specifiers
                    # Matches "package" or "package>=1.0" or "package[extra]>=1.0"
                    deps = re.findall(r'"([a-zA-Z0-9_-]+)(?:\[[^\]]*\])?(?:[><=!~][^"]*)?', content)
                    dependencies.update(deps)
                except (OSError, UnicodeDecodeError):
                    pass

            # Check requirements.txt
            requirements = project_root / "requirements.txt"
            if requirements.exists():
                try:
                    content = requirements.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Extract package name before version specifier
                            match = re.match(r"([a-zA-Z0-9_-]+)", line)
                            if match:
                                dependencies.add(match.group(1))
                except (OSError, UnicodeDecodeError):
                    pass

        elif stack_id == "node":
            # Check package.json
            package_json = project_root / "package.json"
            if package_json.exists():
                try:
                    content = package_json.read_text(encoding="utf-8")
                    # Extract from dependencies and devDependencies
                    deps = re.findall(r'"([a-zA-Z0-9@/_-]+)"\s*:', content)
                    dependencies.update(deps)
                except (OSError, UnicodeDecodeError):
                    pass

        return dependencies
