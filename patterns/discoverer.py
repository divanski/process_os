"""
Pattern discoverer for finding integration patterns in existing code.

This module discovers integration patterns by:
1. Searching for directories containing similar integrations
2. Finding files matching integration type hints
3. Extracting patterns from discovered files
4. Building complete IntegrationPattern objects
"""

import re
from pathlib import Path
from typing import Optional

from process_os.architecture import ProjectArchitecture, ProgrammingLanguage

from process_os.patterns.types import (
    IntegrationPattern,
    PatternComponent,
    ComponentRelationship,
    RegistrationPattern,
)
from process_os.patterns.extractor import PatternExtractor
from process_os.patterns.errors import NoSimilarIntegrationsError, PatternDiscoveryError


class PatternDiscoverer:
    """Discovers integration patterns from existing code.

    Analyzes a project to find existing similar integrations and
    extract architectural patterns that can be used for generating
    new integrations.

    Example:
        >>> discoverer = PatternDiscoverer()
        >>> pattern = discoverer.discover(
        ...     architecture=architecture,
        ...     integration_type="courier",
        ...     search_hints=["adapter", "shipping"],
        ... )
        >>> print(pattern.components)
    """

    # Framework-specific search directories
    FRAMEWORK_DIRECTORIES = {
        "laravel": {
            "services": ["app/Services", "app/Integrations"],
            "contracts": ["app/Contracts", "app/Interfaces"],
            "adapters": ["app/Services/*/Adapters", "app/Adapters"],
        },
        "django": {
            "services": ["services", "apps/*/services"],
            "adapters": ["adapters", "apps/*/adapters"],
        },
        "express": {
            "services": ["src/services", "services"],
            "adapters": ["src/adapters", "adapters"],
        },
    }

    # Common integration-related keywords
    INTEGRATION_KEYWORDS = {
        "courier": ["courier", "shipping", "delivery", "carrier", "freight"],
        "payment": ["payment", "billing", "checkout", "stripe", "paypal"],
        "notification": ["notification", "email", "sms", "push", "alert"],
        "storage": ["storage", "upload", "file", "s3", "blob"],
        "auth": ["auth", "oauth", "sso", "identity", "login"],
    }

    def __init__(self):
        """Initialize the pattern discoverer."""
        self._extractor = PatternExtractor()

    def discover(
        self,
        architecture: ProjectArchitecture,
        integration_type: str,
        search_hints: Optional[list[str]] = None,
    ) -> IntegrationPattern:
        """Discover integration pattern from existing code.

        Args:
            architecture: Project architecture information
            integration_type: Type of integration (e.g., "courier", "payment")
            search_hints: Optional hints for finding integrations

        Returns:
            IntegrationPattern describing the discovered pattern

        Raises:
            NoSimilarIntegrationsError: If no similar integrations found
            PatternDiscoveryError: If discovery fails
        """
        search_hints = search_hints or []

        # Expand search hints with known keywords
        expanded_hints = self._expand_search_hints(integration_type, search_hints)

        # Find integration directories - must match the primary integration type
        integration_dirs = self._find_integration_directories(
            architecture, integration_type, expanded_hints
        )

        # Verify that found directories actually match the integration type
        primary_hint = integration_type.lower()
        verified_dirs = []
        for dir_path in integration_dirs:
            # Directory name must contain the primary integration type
            if primary_hint in dir_path.name.lower():
                verified_dirs.append(dir_path)

        if not verified_dirs:
            raise NoSimilarIntegrationsError(
                f"No similar integrations found for type '{integration_type}'",
                integration_type=integration_type,
                search_hints=search_hints,
            )

        # Find source files in discovered directories
        source_files = self._find_source_files(verified_dirs, architecture.language)

        if not source_files:
            raise NoSimilarIntegrationsError(
                f"No source files found in integration directories",
                integration_type=integration_type,
                search_hints=search_hints,
            )

        # Categorize files by type (adapters, services, interfaces)
        categorized_files = self._categorize_files(source_files)

        # Extract components
        components = self._extractor.extract_components(
            source_files, architecture.language
        )

        if not components:
            raise PatternDiscoveryError(
                "Failed to extract components from source files",
                integration_type=integration_type,
            )

        # Extract relationships
        relationships = self._extractor.extract_relationships(components, architecture)

        # Detect registration pattern
        registration = self._detect_registration_pattern(
            architecture, integration_type, categorized_files
        )

        # Calculate confidence based on evidence
        confidence = self._calculate_confidence(
            components, relationships, source_files
        )

        # Generate pattern name
        pattern_name = self._generate_pattern_name(integration_type, components)

        return IntegrationPattern(
            pattern_name=pattern_name,
            integration_type=integration_type,
            components=components,
            relationships=relationships,
            registration=registration,
            source_examples=source_files,
            confidence=confidence,
        )

    def _expand_search_hints(
        self, integration_type: str, search_hints: list[str]
    ) -> list[str]:
        """Expand search hints with known keywords for the integration type.

        Args:
            integration_type: Type of integration
            search_hints: User-provided hints

        Returns:
            Expanded list of search hints
        """
        hints = set(search_hints)

        # Add integration type itself
        hints.add(integration_type.lower())

        # Add known keywords for this integration type
        if integration_type.lower() in self.INTEGRATION_KEYWORDS:
            hints.update(self.INTEGRATION_KEYWORDS[integration_type.lower()])

        # Add common component suffixes
        hints.update(["adapter", "service", "interface", "contract"])

        return list(hints)

    def _find_integration_directories(
        self,
        architecture: ProjectArchitecture,
        integration_type: str,
        search_hints: list[str],
    ) -> list[Path]:
        """Find directories containing similar integrations.

        Args:
            architecture: Project architecture
            integration_type: Type of integration
            search_hints: Hints for finding directories

        Returns:
            List of directory paths
        """
        found_dirs = []
        root = architecture.get_effective_path()

        # Primary hint is the integration type itself
        primary_hint = integration_type.lower()

        # Get framework-specific directories
        framework_name = architecture.framework.value if architecture.framework else ""
        framework_dirs = self.FRAMEWORK_DIRECTORIES.get(framework_name, {})

        # Search in framework-specific locations
        for dir_type, patterns in framework_dirs.items():
            for pattern in patterns:
                # Replace wildcards with actual search
                if "*" in pattern:
                    base_parts = pattern.split("*")
                    base_path = root / base_parts[0].rstrip("/")
                    if base_path.exists():
                        for subdir in base_path.iterdir():
                            if subdir.is_dir():
                                target = subdir / base_parts[1].lstrip("/")
                                if target.exists():
                                    found_dirs.append(target)
                else:
                    target = root / pattern
                    if target.exists():
                        found_dirs.append(target)

        # Search recursively for directories matching primary hint or other hints
        for path in root.rglob("*"):
            if not path.is_dir():
                continue

            path_name_lower = path.name.lower()

            # Must match primary hint or one of the secondary hints
            matches_hint = primary_hint in path_name_lower
            if not matches_hint:
                for hint in search_hints:
                    if hint.lower() in path_name_lower:
                        matches_hint = True
                        break

            if matches_hint and path not in found_dirs:
                found_dirs.append(path)

        # Filter to directories that contain relevant files and match integration type
        relevant_dirs = []
        for dir_path in found_dirs:
            # Check if directory has integration files
            if not self._directory_has_integration_files(dir_path, architecture.language):
                continue

            # For unknown integration types, require that the directory name matches
            if primary_hint not in dir_path.name.lower():
                # Check if any secondary hint matches the directory structure
                matched = False
                for hint in search_hints:
                    if hint.lower() in str(dir_path).lower():
                        matched = True
                        break
                if not matched and primary_hint not in dir_path.name.lower():
                    continue

            relevant_dirs.append(dir_path)

        return relevant_dirs

    def _directory_has_integration_files(
        self, dir_path: Path, language: ProgrammingLanguage
    ) -> bool:
        """Check if a directory contains integration-related files.

        Args:
            dir_path: Directory to check
            language: Programming language

        Returns:
            True if directory has relevant files
        """
        extensions = self._get_language_extensions(language)

        for ext in extensions:
            files = list(dir_path.glob(f"*{ext}"))
            if files:
                # Check if any file looks like an integration component
                for f in files:
                    name = f.stem.lower()
                    if any(
                        indicator.lower() in name
                        for indicators in PatternExtractor.COMPONENT_INDICATORS.values()
                        for indicator in indicators
                    ):
                        return True

        return False

    def _find_source_files(
        self, directories: list[Path], language: ProgrammingLanguage
    ) -> list[Path]:
        """Find source files in the given directories.

        Args:
            directories: List of directories to search
            language: Programming language

        Returns:
            List of source file paths
        """
        files = []
        extensions = self._get_language_extensions(language)

        for dir_path in directories:
            for ext in extensions:
                files.extend(dir_path.rglob(f"*{ext}"))

        return list(set(files))

    def _categorize_files(self, files: list[Path]) -> dict[str, list[Path]]:
        """Categorize files by component type.

        Args:
            files: List of file paths

        Returns:
            Dict mapping component type to file list
        """
        categories = {
            "adapters": [],
            "services": [],
            "interfaces": [],
            "other": [],
        }

        for file_path in files:
            name = file_path.stem.lower()

            if "adapter" in name or "driver" in name or "gateway" in name:
                categories["adapters"].append(file_path)
            elif "service" in name or "manager" in name:
                categories["services"].append(file_path)
            elif "interface" in name or "contract" in name:
                categories["interfaces"].append(file_path)
            else:
                categories["other"].append(file_path)

        return categories

    def _detect_registration_pattern(
        self,
        architecture: ProjectArchitecture,
        integration_type: str,
        categorized_files: dict[str, list[Path]],
    ) -> Optional[RegistrationPattern]:
        """Detect how integrations are registered in the project.

        Args:
            architecture: Project architecture
            integration_type: Type of integration
            categorized_files: Files categorized by type

        Returns:
            RegistrationPattern or None
        """
        root = architecture.get_effective_path()

        # Look for Laravel service providers
        if architecture.framework and architecture.framework.value == "laravel":
            providers_dir = root / "app" / "Providers"
            if providers_dir.exists():
                # Search for provider related to integration type
                for provider in providers_dir.glob("*ServiceProvider.php"):
                    if integration_type.lower() in provider.stem.lower():
                        return RegistrationPattern(
                            registration_type="service_provider",
                            file_path=provider,
                            pattern_template="$this->app->bind('{Name}AdapterInterface', {ClassName}::class);",
                        )

        return None

    def _calculate_confidence(
        self,
        components: list[PatternComponent],
        relationships: list[ComponentRelationship],
        source_files: list[Path],
    ) -> float:
        """Calculate confidence score for the discovered pattern.

        Args:
            components: Discovered components
            relationships: Discovered relationships
            source_files: Source files found

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0

        # Base score for having any components
        if components:
            score += 0.3

        # Bonus for multiple examples (indicates established pattern)
        adapter_count = sum(1 for c in components if c.component_type == "adapter")
        if adapter_count >= 2:
            score += 0.2
        elif adapter_count >= 1:
            score += 0.1

        # Bonus for interface/contract
        has_interface = any(c.component_type == "interface" for c in components)
        if has_interface:
            score += 0.2

        # Bonus for service layer
        has_service = any(c.component_type == "service" for c in components)
        if has_service:
            score += 0.1

        # Bonus for relationships
        if relationships:
            score += 0.1 * min(len(relationships), 2)

        return min(score, 1.0)

    def _generate_pattern_name(
        self, integration_type: str, components: list[PatternComponent]
    ) -> str:
        """Generate a descriptive name for the pattern.

        Args:
            integration_type: Type of integration
            components: Discovered components

        Returns:
            Pattern name string
        """
        # Capitalize integration type
        name = integration_type.title()

        # Add primary component type
        if any(c.component_type == "adapter" for c in components):
            name += "Adapter"
        elif any(c.component_type == "service" for c in components):
            name += "Service"

        return name

    def _get_language_extensions(self, language: ProgrammingLanguage) -> list[str]:
        """Get file extensions for a programming language.

        Args:
            language: Programming language

        Returns:
            List of file extensions
        """
        extensions = {
            ProgrammingLanguage.PHP: [".php"],
            ProgrammingLanguage.PYTHON: [".py"],
            ProgrammingLanguage.JAVASCRIPT: [".js", ".mjs"],
            ProgrammingLanguage.TYPESCRIPT: [".ts", ".tsx"],
            ProgrammingLanguage.RUBY: [".rb"],
            ProgrammingLanguage.JAVA: [".java"],
        }

        return extensions.get(language, [])


def discover_integration_pattern(
    architecture: ProjectArchitecture,
    integration_type: str,
    search_hints: Optional[list[str]] = None,
) -> IntegrationPattern:
    """Convenience function to discover an integration pattern.

    Args:
        architecture: Project architecture
        integration_type: Type of integration
        search_hints: Optional search hints

    Returns:
        IntegrationPattern for the discovered pattern

    Raises:
        NoSimilarIntegrationsError: If no similar integrations found
    """
    discoverer = PatternDiscoverer()
    return discoverer.discover(architecture, integration_type, search_hints)
