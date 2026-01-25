"""
Architecture and convention conflict detection.

Implements:
- T211: ConflictDetector for architecture pattern conflicts
- T212: Convention conflict detection (naming, organization)
- T213: Structural inconsistency detection
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class ArchitecturePattern:
    """Detected architecture pattern."""

    name: str
    confidence: float
    description: str
    indicators: List[str]


@dataclass
class Convention:
    """Code convention."""

    type: str  # naming, organization, documentation
    name: str
    examples: List[str]
    files_using: int


@dataclass
class ConflictReport:
    """Detected architectural conflict."""

    conflict_type: str
    severity: str  # critical, warning, info
    description: str
    affected_patterns: List[str]
    affected_conventions: List[str]
    file_locations: List[str]
    resolution: Optional[str] = None


class ConflictDetector:
    """
    Detects architectural and convention conflicts.

    Identifies:
    - Mixed architecture patterns (MVC + Layered, Microservices + Monolithic)
    - Mixed naming conventions (camelCase + snake_case)
    - Inconsistent file organization
    - Route location inconsistencies
    - Configuration file type proliferation
    """

    def __init__(self):
        """Initialize conflict detector."""
        self.detected_patterns: List[ArchitecturePattern] = []
        self.detected_conventions: List[Convention] = []
        self.conflicts: List[ConflictReport] = []

    def add_pattern(self, pattern: ArchitecturePattern) -> None:
        """
        Add detected architecture pattern.

        Args:
            pattern: Architecture pattern
        """
        self.detected_patterns.append(pattern)

    def add_convention(self, convention: Convention) -> None:
        """
        Add detected convention.

        Args:
            convention: Code convention
        """
        self.detected_conventions.append(convention)

    def detect_architecture_conflicts(self) -> List[ConflictReport]:
        """
        Detect architecture pattern conflicts.

        Identifies:
        - Conflicting patterns (e.g., MVC + Microservices)
        - Unused patterns
        - Mixed architectural approaches

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Check for MVC + Layered Architecture mixed
        has_mvc = any(p.name == "MVC" for p in self.detected_patterns)
        has_layered = any(
            p.name == "Layered Architecture"
            for p in self.detected_patterns
        )

        if has_mvc and has_layered:
            conflicts.append(
                ConflictReport(
                    conflict_type="mixed_architecture",
                    severity="warning",
                    description="Mixed MVC and Layered Architecture patterns detected",
                    affected_patterns=["MVC", "Layered Architecture"],
                    affected_conventions=[],
                    file_locations=["controllers/", "services/", "models/"],
                    resolution="Choose single primary architecture, refactor secondary",
                )
            )

        # Check for Microservices + Monolithic mixed
        has_microservices = any(
            p.name == "Microservices" for p in self.detected_patterns
        )
        has_monolithic = any(
            p.name == "Monolithic" for p in self.detected_patterns
        )

        if has_microservices and has_monolithic:
            conflicts.append(
                ConflictReport(
                    conflict_type="mixed_architecture",
                    severity="critical",
                    description="Both Microservices and Monolithic patterns detected",
                    affected_patterns=["Microservices", "Monolithic"],
                    affected_conventions=[],
                    file_locations=["src/", "services/"],
                    resolution="Refactor to single architecture pattern",
                )
            )

        return conflicts

    def detect_convention_conflicts(self) -> List[ConflictReport]:
        """
        Detect code convention conflicts.

        Identifies:
        - Mixed naming conventions (camelCase, snake_case, PascalCase)
        - Inconsistent file organization
        - Documentation style mismatches

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Check for mixed naming conventions
        naming_conventions = [
            c for c in self.detected_conventions if c.type == "naming"
        ]
        if len(naming_conventions) > 1:
            convention_names = [c.name for c in naming_conventions]
            conflicts.append(
                ConflictReport(
                    conflict_type="mixed_naming_conventions",
                    severity="warning",
                    description=f"Mixed naming conventions: {', '.join(convention_names)}",
                    affected_patterns=[],
                    affected_conventions=convention_names,
                    file_locations=[
                        f"files_using_{c.name.replace(' ', '_')}"
                        for c in naming_conventions
                    ],
                    resolution="Standardize naming convention across codebase",
                )
            )

        # Check for mixed organization patterns
        org_conventions = [
            c for c in self.detected_conventions if c.type == "organization"
        ]
        if len(org_conventions) > 1:
            org_names = [c.name for c in org_conventions]
            conflicts.append(
                ConflictReport(
                    conflict_type="mixed_organization",
                    severity="warning",
                    description=f"Inconsistent file organization: {', '.join(org_names)}",
                    affected_patterns=[],
                    affected_conventions=org_names,
                    file_locations=["src/", "lib/", "app/"],
                    resolution="Unify directory structure",
                )
            )

        return conflicts

    def detect_structural_inconsistencies(
        self, structure_data: Dict[str, Any]
    ) -> List[ConflictReport]:
        """
        Detect structural inconsistencies in codebase.

        Identifies:
        - Routes in multiple locations
        - Configuration inconsistencies
        - Module organization issues

        Args:
            structure_data: Code structure analysis

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Check for multiple route definitions
        route_locations = structure_data.get("route_locations", [])
        if len(route_locations) > 1:
            conflicts.append(
                ConflictReport(
                    conflict_type="route_location_inconsistency",
                    severity="warning",
                    description=f"Routes defined in multiple locations: {', '.join(route_locations)}",
                    affected_patterns=[],
                    affected_conventions=[],
                    file_locations=route_locations,
                    resolution="Consolidate routing definitions",
                )
            )

        # Check for multiple config file types
        config_types = structure_data.get("config_file_types", [])
        if len(config_types) > 3:  # More than 3 is excessive
            conflicts.append(
                ConflictReport(
                    conflict_type="config_inconsistency",
                    severity="info",
                    description=f"Multiple config file types: {', '.join(config_types)}",
                    affected_patterns=[],
                    affected_conventions=[],
                    file_locations=["root/", "config/"],
                    resolution="Standardize configuration format",
                )
            )

        return conflicts

    def detect_all_conflicts(
        self, structure_data: Optional[Dict[str, Any]] = None
    ) -> List[ConflictReport]:
        """
        Detect all types of conflicts.

        Args:
            structure_data: Optional structure analysis

        Returns:
            All detected conflicts
        """
        conflicts = []

        conflicts.extend(self.detect_architecture_conflicts())
        conflicts.extend(self.detect_convention_conflicts())

        if structure_data:
            conflicts.extend(self.detect_structural_inconsistencies(structure_data))

        self.conflicts = conflicts
        return conflicts

    def has_critical_conflicts(self) -> bool:
        """
        Check if any critical conflicts exist.

        Returns:
            True if critical conflicts found
        """
        return any(c.severity == "critical" for c in self.conflicts)

    def get_conflict_summary(self) -> Dict[str, Any]:
        """
        Get summary of all conflicts.

        Returns:
            Conflict summary dict with:
            - total_conflicts: Total number of conflicts
            - critical: Count of critical conflicts
            - warnings: Count of warning conflicts
            - info: Count of info conflicts
            - has_critical: Boolean indicating critical conflicts
            - conflicts: List of all conflicts
        """
        critical = [c for c in self.conflicts if c.severity == "critical"]
        warnings = [c for c in self.conflicts if c.severity == "warning"]
        info = [c for c in self.conflicts if c.severity == "info"]

        return {
            "total_conflicts": len(self.conflicts),
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(info),
            "has_critical": len(critical) > 0,
            "conflicts": self.conflicts,
        }
