"""
ProcessOS Discovery Context Module

Core data models for project structure discovery.
Provides comprehensive understanding of a project's architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ModelField:
    """A field within a model."""

    name: str
    field_type: str  # string, integer, datetime, etc.
    nullable: bool = False
    default: Optional[Any] = None
    constraints: List[str] = field(default_factory=list)  # unique, indexed, etc.


@dataclass
class Relationship:
    """A relationship between models."""

    type: str  # 'foreign_key', 'one_to_many', 'many_to_many'
    target_model: str
    field_name: str
    reverse_name: Optional[str] = None


@dataclass
class LocalModel:
    """A discovered database model/entity in the project."""

    name: str
    file_path: Path
    line_number: int
    fields: List[ModelField] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    table_name: Optional[str] = None


@dataclass
class RouteParameter:
    """A parameter in a route."""

    name: str
    location: str  # 'path', 'query', 'body'
    param_type: Optional[str] = None
    required: bool = True


@dataclass
class Route:
    """A discovered API route/endpoint."""

    method: str  # HTTP method (GET, POST, etc.)
    path: str  # URL path pattern
    handler: str  # Function/method name
    file_path: Path
    line_number: int
    parameters: List[RouteParameter] = field(default_factory=list)
    auth_required: Optional[bool] = None


@dataclass
class Service:
    """A discovered service/business logic component."""

    name: str
    file_path: Path
    line_number: int
    service_type: str  # 'class', 'module', 'function'
    methods: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ExistingIntegration:
    """An existing external service integration in the project."""

    service_name: str  # e.g., "Stripe", "AWS S3"
    integration_type: str  # 'payment', 'storage', 'notification'
    file_paths: List[Path] = field(default_factory=list)
    patterns_used: List[str] = field(default_factory=list)  # e.g., 'service_class', 'direct_api'


@dataclass
class ProjectConventions:
    """Detected coding conventions and patterns."""

    # Naming
    class_naming: str = "PascalCase"
    function_naming: str = "snake_case"
    file_naming: str = "snake_case"

    # Structure
    service_pattern: Optional[str] = None  # 'service_classes', 'modules', 'functions'
    repository_pattern: bool = False
    dependency_injection: bool = False

    # Code Style
    import_style: str = "absolute"  # 'absolute', 'relative'
    docstring_style: Optional[str] = None  # 'google', 'numpy', 'sphinx'
    type_hints: bool = False

    # Examples (actual code snippets for reference)
    example_service: Optional[str] = None
    example_model: Optional[str] = None


@dataclass
class DiscoveryConfig:
    """Configuration for project discovery."""

    root_path: Path
    max_file_count: int = 10000
    target_subdirectory: Optional[Path] = None  # For --target-dir flag
    include_patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts", "**/*.php"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["**/node_modules/**", "**/.git/**", "**/vendor/**", "**/__pycache__/**"])
    detect_models: bool = True
    detect_routes: bool = True
    detect_services: bool = True
    detect_integrations: bool = True


@dataclass
class ProjectContext:
    """Complete project architecture understanding."""

    # Identification
    project_id: str  # Unique identifier (hash of root path)
    root_path: Path
    discovered_at: datetime
    discovery_version: str = "1.0.0"

    # Stack Information (from existing stack_fingerprint)
    language: str = ""  # Primary language (python, javascript, php)
    language_version: Optional[str] = None
    framework: Optional[str] = None  # Primary framework (django, express, laravel)
    framework_version: Optional[str] = None
    package_manager: Optional[str] = None  # pip, npm, composer

    # Deep Discovery
    models: List[LocalModel] = field(default_factory=list)
    routes: List[Route] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    existing_integrations: List[ExistingIntegration] = field(default_factory=list)

    # Conventions
    conventions: ProjectConventions = field(default_factory=ProjectConventions)

    # Statistics
    file_count: int = 0
    analysis_duration_ms: int = 0

    # Confidence
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "project_id": self.project_id,
            "root_path": str(self.root_path),
            "discovered_at": self.discovered_at.isoformat(),
            "discovery_version": self.discovery_version,
            "language": self.language,
            "language_version": self.language_version,
            "framework": self.framework,
            "framework_version": self.framework_version,
            "package_manager": self.package_manager,
            "models": [self._model_to_dict(m) for m in self.models],
            "routes": [self._route_to_dict(r) for r in self.routes],
            "services": [self._service_to_dict(s) for s in self.services],
            "existing_integrations": [self._integration_to_dict(i) for i in self.existing_integrations],
            "conventions": self._conventions_to_dict(self.conventions),
            "file_count": self.file_count,
            "analysis_duration_ms": self.analysis_duration_ms,
            "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectContext":
        """Deserialize from dictionary."""
        return cls(
            project_id=data["project_id"],
            root_path=Path(data["root_path"]),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            discovery_version=data.get("discovery_version", "1.0.0"),
            language=data.get("language", ""),
            language_version=data.get("language_version"),
            framework=data.get("framework"),
            framework_version=data.get("framework_version"),
            package_manager=data.get("package_manager"),
            models=[cls._dict_to_model(m) for m in data.get("models", [])],
            routes=[cls._dict_to_route(r) for r in data.get("routes", [])],
            services=[cls._dict_to_service(s) for s in data.get("services", [])],
            existing_integrations=[cls._dict_to_integration(i) for i in data.get("existing_integrations", [])],
            conventions=cls._dict_to_conventions(data.get("conventions", {})),
            file_count=data.get("file_count", 0),
            analysis_duration_ms=data.get("analysis_duration_ms", 0),
            confidence_score=data.get("confidence_score", 0.0),
        )

    @staticmethod
    def _model_to_dict(model: LocalModel) -> Dict[str, Any]:
        return {
            "name": model.name,
            "file_path": str(model.file_path),
            "line_number": model.line_number,
            "fields": [
                {
                    "name": f.name,
                    "field_type": f.field_type,
                    "nullable": f.nullable,
                    "default": f.default,
                    "constraints": f.constraints,
                }
                for f in model.fields
            ],
            "relationships": [
                {
                    "type": r.type,
                    "target_model": r.target_model,
                    "field_name": r.field_name,
                    "reverse_name": r.reverse_name,
                }
                for r in model.relationships
            ],
            "table_name": model.table_name,
        }

    @staticmethod
    def _dict_to_model(data: Dict[str, Any]) -> LocalModel:
        return LocalModel(
            name=data["name"],
            file_path=Path(data["file_path"]),
            line_number=data["line_number"],
            fields=[
                ModelField(
                    name=f["name"],
                    field_type=f["field_type"],
                    nullable=f.get("nullable", False),
                    default=f.get("default"),
                    constraints=f.get("constraints", []),
                )
                for f in data.get("fields", [])
            ],
            relationships=[
                Relationship(
                    type=r["type"],
                    target_model=r["target_model"],
                    field_name=r["field_name"],
                    reverse_name=r.get("reverse_name"),
                )
                for r in data.get("relationships", [])
            ],
            table_name=data.get("table_name"),
        )

    @staticmethod
    def _route_to_dict(route: Route) -> Dict[str, Any]:
        return {
            "method": route.method,
            "path": route.path,
            "handler": route.handler,
            "file_path": str(route.file_path),
            "line_number": route.line_number,
            "parameters": [
                {
                    "name": p.name,
                    "location": p.location,
                    "param_type": p.param_type,
                    "required": p.required,
                }
                for p in route.parameters
            ],
            "auth_required": route.auth_required,
        }

    @staticmethod
    def _dict_to_route(data: Dict[str, Any]) -> Route:
        return Route(
            method=data["method"],
            path=data["path"],
            handler=data["handler"],
            file_path=Path(data["file_path"]),
            line_number=data["line_number"],
            parameters=[
                RouteParameter(
                    name=p["name"],
                    location=p["location"],
                    param_type=p.get("param_type"),
                    required=p.get("required", True),
                )
                for p in data.get("parameters", [])
            ],
            auth_required=data.get("auth_required"),
        )

    @staticmethod
    def _service_to_dict(service: Service) -> Dict[str, Any]:
        return {
            "name": service.name,
            "file_path": str(service.file_path),
            "line_number": service.line_number,
            "service_type": service.service_type,
            "methods": service.methods,
            "dependencies": service.dependencies,
        }

    @staticmethod
    def _dict_to_service(data: Dict[str, Any]) -> Service:
        return Service(
            name=data["name"],
            file_path=Path(data["file_path"]),
            line_number=data["line_number"],
            service_type=data["service_type"],
            methods=data.get("methods", []),
            dependencies=data.get("dependencies", []),
        )

    @staticmethod
    def _integration_to_dict(integration: ExistingIntegration) -> Dict[str, Any]:
        return {
            "service_name": integration.service_name,
            "integration_type": integration.integration_type,
            "file_paths": [str(p) for p in integration.file_paths],
            "patterns_used": integration.patterns_used,
        }

    @staticmethod
    def _dict_to_integration(data: Dict[str, Any]) -> ExistingIntegration:
        return ExistingIntegration(
            service_name=data["service_name"],
            integration_type=data["integration_type"],
            file_paths=[Path(p) for p in data.get("file_paths", [])],
            patterns_used=data.get("patterns_used", []),
        )

    @staticmethod
    def _conventions_to_dict(conventions: ProjectConventions) -> Dict[str, Any]:
        return {
            "class_naming": conventions.class_naming,
            "function_naming": conventions.function_naming,
            "file_naming": conventions.file_naming,
            "service_pattern": conventions.service_pattern,
            "repository_pattern": conventions.repository_pattern,
            "dependency_injection": conventions.dependency_injection,
            "import_style": conventions.import_style,
            "docstring_style": conventions.docstring_style,
            "type_hints": conventions.type_hints,
            "example_service": conventions.example_service,
            "example_model": conventions.example_model,
        }

    @staticmethod
    def _dict_to_conventions(data: Dict[str, Any]) -> ProjectConventions:
        return ProjectConventions(
            class_naming=data.get("class_naming", "PascalCase"),
            function_naming=data.get("function_naming", "snake_case"),
            file_naming=data.get("file_naming", "snake_case"),
            service_pattern=data.get("service_pattern"),
            repository_pattern=data.get("repository_pattern", False),
            dependency_injection=data.get("dependency_injection", False),
            import_style=data.get("import_style", "absolute"),
            docstring_style=data.get("docstring_style"),
            type_hints=data.get("type_hints", False),
            example_service=data.get("example_service"),
            example_model=data.get("example_model"),
        )
