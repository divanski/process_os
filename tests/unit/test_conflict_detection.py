"""
Unit tests for architecture conflict detection.

Tests for Phase 8 (Polish & Integration): Conflict detection

Tests:
- T180-T188: Conflict detection algorithms
"""

import pytest
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
    """Detects architectural and convention conflicts."""

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
        - Mixed naming conventions
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
            Conflict summary dict
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


class TestArchitectureConflictDetection:
    """Test architecture pattern conflict detection (T180-T182)."""

    def test_mvc_and_layered_architecture_conflict(self):
        """Verify MVC + Layered Architecture detected as conflict (T180)."""
        detector = ConflictDetector()

        # Add MVC pattern
        detector.add_pattern(
            ArchitecturePattern(
                name="MVC",
                confidence=0.85,
                description="Model-View-Controller pattern detected",
                indicators=["controllers/", "models/", "views/"],
            )
        )

        # Add Layered Architecture pattern
        detector.add_pattern(
            ArchitecturePattern(
                name="Layered Architecture",
                confidence=0.80,
                description="Layered architecture with clear tiers",
                indicators=["presentation/", "business/", "persistence/"],
            )
        )

        # Detect conflicts
        conflicts = detector.detect_architecture_conflicts()

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "mixed_architecture"
        assert conflicts[0].severity == "warning"
        assert "MVC" in conflicts[0].affected_patterns
        assert "Layered Architecture" in conflicts[0].affected_patterns

    def test_microservices_monolithic_conflict_critical(self):
        """Verify Microservices + Monolithic conflict marked critical (T181)."""
        detector = ConflictDetector()

        detector.add_pattern(
            ArchitecturePattern(
                name="Microservices",
                confidence=0.90,
                description="Microservices architecture",
                indicators=["services/", "api/", "docker-compose.yml"],
            )
        )

        detector.add_pattern(
            ArchitecturePattern(
                name="Monolithic",
                confidence=0.85,
                description="Monolithic architecture",
                indicators=["src/app.py", "single_codebase"],
            )
        )

        conflicts = detector.detect_architecture_conflicts()

        assert len(conflicts) == 1
        assert conflicts[0].severity == "critical"
        assert conflicts[0].conflict_type == "mixed_architecture"

    def test_no_conflicts_with_single_architecture(self):
        """Verify no conflicts when single architecture detected (T182)."""
        detector = ConflictDetector()

        detector.add_pattern(
            ArchitecturePattern(
                name="MVC",
                confidence=0.85,
                description="Model-View-Controller",
                indicators=["controllers/", "models/", "views/"],
            )
        )

        conflicts = detector.detect_architecture_conflicts()

        assert len(conflicts) == 0


class TestConventionConflictDetection:
    """Test naming and convention conflict detection (T183-T185)."""

    def test_mixed_naming_conventions_detected(self):
        """Verify mixed naming conventions detected as conflict (T183)."""
        detector = ConflictDetector()

        # Add camelCase convention
        detector.add_convention(
            Convention(
                type="naming",
                name="camelCase",
                examples=["userId", "getUserData", "setUserName"],
                files_using=45,
            )
        )

        # Add snake_case convention
        detector.add_convention(
            Convention(
                type="naming",
                name="snake_case",
                examples=["user_id", "get_user_data", "set_user_name"],
                files_using=35,
            )
        )

        conflicts = detector.detect_convention_conflicts()

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "mixed_naming_conventions"
        assert conflicts[0].severity == "warning"
        assert "camelCase" in conflicts[0].affected_conventions
        assert "snake_case" in conflicts[0].affected_conventions

    def test_mixed_organization_patterns(self):
        """Verify mixed file organization detected (T184)."""
        detector = ConflictDetector()

        # Add directory-based organization
        detector.add_convention(
            Convention(
                type="organization",
                name="directory_by_type",
                examples=["src/models/", "src/controllers/", "src/views/"],
                files_using=120,
            )
        )

        # Add feature-based organization
        detector.add_convention(
            Convention(
                type="organization",
                name="directory_by_feature",
                examples=["features/users/", "features/products/"],
                files_using=80,
            )
        )

        conflicts = detector.detect_convention_conflicts()

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "mixed_organization"

    def test_multiple_conventions_same_type_ok(self):
        """Verify documentation conventions don't conflict (T185)."""
        detector = ConflictDetector()

        detector.add_convention(
            Convention(
                type="documentation",
                name="docstring_style",
                examples=["Google-style docstrings"],
                files_using=100,
            )
        )

        detector.add_convention(
            Convention(
                type="documentation",
                name="inline_comments",
                examples=["// Implementation note"],
                files_using=50,
            )
        )

        conflicts = detector.detect_convention_conflicts()

        # Documentation style variations acceptable
        assert len(conflicts) == 0


class TestStructuralConsistencyDetection:
    """Test structural inconsistency detection (T186-T188)."""

    def test_routes_in_multiple_locations_detected(self):
        """Verify routes in multiple locations detected (T186)."""
        detector = ConflictDetector()

        structure = {
            "route_locations": ["app/routes.py", "controllers/routes.py", "api/v1/routes.py"],
            "config_file_types": ["config.py", "config.yaml"],
        }

        conflicts = detector.detect_structural_inconsistencies(structure)

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "route_location_inconsistency"
        assert conflicts[0].severity == "warning"

    def test_excessive_config_file_types(self):
        """Verify excessive config formats detected (T187)."""
        detector = ConflictDetector()

        structure = {
            "route_locations": ["routes.py"],
            "config_file_types": [
                "config.yaml",
                "config.json",
                "config.toml",
                ".env",
                "settings.py",
            ],
        }

        conflicts = detector.detect_structural_inconsistencies(structure)

        assert any(c.conflict_type == "config_inconsistency" for c in conflicts)

    def test_detect_all_conflicts_together(self):
        """Verify all conflict types detected together (T188)."""
        detector = ConflictDetector()

        # Add patterns
        detector.add_pattern(
            ArchitecturePattern(
                name="MVC",
                confidence=0.85,
                description="MVC",
                indicators=["controllers/"],
            )
        )

        detector.add_pattern(
            ArchitecturePattern(
                name="Layered Architecture",
                confidence=0.80,
                description="Layered",
                indicators=["business/"],
            )
        )

        # Add conventions
        detector.add_convention(
            Convention(
                type="naming",
                name="camelCase",
                examples=["userId"],
                files_using=50,
            )
        )

        detector.add_convention(
            Convention(
                type="naming",
                name="snake_case",
                examples=["user_id"],
                files_using=40,
            )
        )

        # Detect all
        structure = {
            "route_locations": ["routes.py", "controllers/routes.py"],
            "config_file_types": ["yaml", "json", "toml"],
        }

        all_conflicts = detector.detect_all_conflicts(structure)

        assert len(all_conflicts) >= 3  # At least arch + convention + structural

        assert any(
            c.conflict_type == "mixed_architecture" for c in all_conflicts
        )
        assert any(
            c.conflict_type == "mixed_naming_conventions"
            for c in all_conflicts
        )
        assert any(
            c.conflict_type == "route_location_inconsistency"
            for c in all_conflicts
        )


class TestConflictReporting:
    """Test conflict reporting and summary."""

    def test_conflict_summary_generation(self):
        """Verify conflict summary generated correctly."""
        detector = ConflictDetector()

        detector.add_pattern(
            ArchitecturePattern(
                name="Microservices",
                confidence=0.90,
                description="Microservices",
                indicators=["services/"],
            )
        )

        detector.add_pattern(
            ArchitecturePattern(
                name="Monolithic",
                confidence=0.85,
                description="Monolithic",
                indicators=["src/"],
            )
        )

        detector.detect_all_conflicts()

        summary = detector.get_conflict_summary()

        assert summary["total_conflicts"] == 1
        assert summary["critical"] == 1
        assert summary["has_critical"] is True

    def test_critical_conflict_detection(self):
        """Verify critical conflict flag works."""
        detector = ConflictDetector()

        detector.add_pattern(
            ArchitecturePattern(
                name="Microservices",
                confidence=0.90,
                description="Microservices",
                indicators=["services/"],
            )
        )

        detector.add_pattern(
            ArchitecturePattern(
                name="Monolithic",
                confidence=0.85,
                description="Monolithic",
                indicators=["src/"],
            )
        )

        detector.detect_all_conflicts()

        assert detector.has_critical_conflicts() is True
