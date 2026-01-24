"""
Type definitions for the patterns module.

This module defines data structures for integration pattern discovery:
- Enums for relationship types
- Dataclasses for pattern components, relationships, and integration patterns
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RelationshipType(Enum):
    """Types of relationships between components.

    Used to map how components in an integration pattern relate to each other.
    """

    USES = "uses"  # Service uses Adapter
    IMPLEMENTS = "implements"  # Adapter implements Interface
    EXTENDS = "extends"  # Adapter extends BaseAdapter
    REGISTERED_IN = "registered_in"  # Adapter registered in ServiceProvider
    CONFIGURED_BY = "configured_by"  # Service configured by config file


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_optional: bool = False

    def to_signature(self, language: str = "php") -> str:
        """Generate parameter signature for the given language."""
        if language == "php":
            parts = []
            if self.type_hint:
                parts.append(self.type_hint)
            parts.append(f"${self.name}")
            if self.default_value is not None:
                parts.append(f"= {self.default_value}")
            return " ".join(parts)
        elif language == "python":
            parts = [self.name]
            if self.type_hint:
                parts[0] = f"{self.name}: {self.type_hint}"
            if self.default_value is not None:
                parts.append(f"= {self.default_value}")
            return " ".join(parts)
        else:
            return self.name


@dataclass
class MethodSignature:
    """Signature of a method that must be implemented.

    Used to define interface/abstract methods that new integrations must implement.
    """

    name: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    return_type: Optional[str] = None
    visibility: str = "public"  # public, protected, private
    is_abstract: bool = False
    is_static: bool = False
    docstring: Optional[str] = None

    def to_declaration(self, language: str = "php") -> str:
        """Generate method declaration for the given language."""
        params = ", ".join(p.to_signature(language) for p in self.parameters)

        if language == "php":
            parts = []
            if self.is_abstract:
                parts.append("abstract")
            parts.append(self.visibility)
            if self.is_static:
                parts.append("static")
            parts.append("function")
            parts.append(f"{self.name}({params})")
            if self.return_type:
                parts.append(f": {self.return_type}")
            return " ".join(parts)
        elif language == "python":
            decorator = "@abstractmethod\n    " if self.is_abstract else ""
            static = "@staticmethod\n    " if self.is_static else ""
            ret = f" -> {self.return_type}" if self.return_type else ""
            return f"{decorator}{static}def {self.name}({params}){ret}:"
        else:
            return f"{self.name}({params})"


@dataclass
class PatternComponent:
    """A component of an integration pattern (e.g., Adapter, Service, Contract).

    Represents a single file/class type in the integration pattern.
    """

    component_type: str  # e.g., "adapter", "service", "contract", "interface"
    file_pattern: str  # e.g., "{Name}Adapter.php"
    directory: str  # e.g., "app/Services/Courier/Adapters/"
    namespace: str = ""  # e.g., "App\\Services\\Courier\\Adapters"
    base_class: Optional[str] = None  # e.g., "BaseCourierAdapter"
    interfaces: list[str] = field(default_factory=list)  # e.g., ["CourierAdapterInterface"]
    required_methods: list[MethodSignature] = field(default_factory=list)
    examples: list[Path] = field(default_factory=list)  # existing files of this type
    integration_points: dict = field(default_factory=dict)  # e.g., {"service_provider": True, "config": True}

    def generate_filename(self, name: str) -> str:
        """Generate filename for a new integration with given name."""
        return self.file_pattern.replace("{Name}", name).replace("{name}", name.lower())

    def generate_class_name(self, name: str) -> str:
        """Generate class name for a new integration."""
        # Extract class name from file pattern
        class_pattern = self.file_pattern.replace(".php", "").replace(".py", "").replace(".js", "").replace(".ts", "")
        return class_pattern.replace("{Name}", name).replace("{name}", name.lower())


@dataclass
class ComponentRelationship:
    """Relationship between two pattern components.

    Maps how components in the integration depend on or relate to each other.
    """

    source: str  # component type, e.g., "adapter"
    target: str  # component type, e.g., "service"
    relationship_type: RelationshipType
    description: str = ""  # e.g., "Adapter is injected into Service"


@dataclass
class RegistrationPattern:
    """Pattern for registering new integrations.

    Describes how integrations are registered in the project (e.g., ServiceProvider).
    """

    registration_type: str  # e.g., "service_provider", "config_array", "decorator"
    file_path: Optional[Path] = None  # e.g., "app/Providers/CourierServiceProvider.php"
    pattern_template: str = ""  # code template for registration
    existing_registrations: list[str] = field(default_factory=list)  # examples from existing

    def generate_registration(self, name: str, class_name: str, namespace: str) -> str:
        """Generate registration code for a new integration."""
        return (
            self.pattern_template.replace("{Name}", name)
            .replace("{name}", name.lower())
            .replace("{ClassName}", class_name)
            .replace("{Namespace}", namespace)
        )


@dataclass
class IntegrationPattern:
    """Architectural pattern for a type of integration.

    This is the main data structure that captures everything learned from
    existing similar integrations in the project.
    """

    pattern_name: str  # e.g., "CourierAdapter", "PaymentGateway"
    integration_type: str  # e.g., "courier", "payment", "notification"
    components: list[PatternComponent] = field(default_factory=list)
    relationships: list[ComponentRelationship] = field(default_factory=list)
    registration: Optional[RegistrationPattern] = None
    source_examples: list[Path] = field(default_factory=list)  # files pattern was learned from
    confidence: float = 1.0  # how confident we are in this pattern

    def __post_init__(self):
        """Validate pattern data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def get_component(self, component_type: str) -> Optional[PatternComponent]:
        """Get a specific component by type."""
        for comp in self.components:
            if comp.component_type == component_type:
                return comp
        return None

    def get_required_interfaces(self) -> list[str]:
        """Get all interfaces that must be implemented."""
        interfaces = []
        for comp in self.components:
            interfaces.extend(comp.interfaces)
        return list(set(interfaces))

    def get_component_types(self) -> list[str]:
        """Get all component types in this pattern."""
        return [comp.component_type for comp in self.components]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "pattern_name": self.pattern_name,
            "integration_type": self.integration_type,
            "components": [
                {
                    "component_type": c.component_type,
                    "file_pattern": c.file_pattern,
                    "directory": c.directory,
                    "namespace": c.namespace,
                    "base_class": c.base_class,
                    "interfaces": c.interfaces,
                }
                for c in self.components
            ],
            "relationships": [
                {
                    "source": r.source,
                    "target": r.target,
                    "relationship_type": r.relationship_type.value,
                    "description": r.description,
                }
                for r in self.relationships
            ],
            "source_examples": [str(p) for p in self.source_examples],
            "confidence": self.confidence,
        }
