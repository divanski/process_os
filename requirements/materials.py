"""
ProcessOS Materials Module

Data models for collected integration materials including API documentation,
credentials references, and example payloads.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class APIParameter:
    """An API parameter."""

    name: str
    location: str  # 'path', 'query', 'header'
    param_type: str
    required: bool = True
    description: Optional[str] = None


@dataclass
class APISchema:
    """A schema for request/response body."""

    content_type: str = "application/json"
    schema: Dict[str, Any] = field(default_factory=dict)  # JSON Schema representation
    example: Optional[Any] = None


@dataclass
class APIEndpoint:
    """A parsed API endpoint."""

    method: str  # HTTP method
    path: str  # URL path
    summary: Optional[str] = None

    # Parameters
    parameters: List[APIParameter] = field(default_factory=list)
    request_body: Optional[APISchema] = None
    response_schema: Optional[APISchema] = None

    # Auth
    auth_required: bool = True
    scopes: List[str] = field(default_factory=list)  # OAuth scopes if applicable


@dataclass
class APIDocumentation:
    """Parsed API documentation."""

    source: str  # URL, file path, or 'manual'
    source_type: str  # 'openapi', 'swagger', 'graphql', 'manual'

    # Parsed content
    base_url: Optional[str] = None
    auth_method: Optional[str] = None  # 'api_key', 'oauth2', 'basic'
    endpoints: List[APIEndpoint] = field(default_factory=list)

    # Raw content (for LLM context)
    raw_content: Optional[str] = None


@dataclass
class CredentialReference:
    """Reference to a credential (env var name only, never actual value)."""

    name: str  # Human-readable name
    env_var_name: str  # Environment variable name
    credential_type: str  # 'api_key', 'oauth_client_id', etc.
    description: str  # How this credential is used


@dataclass
class APIExample:
    """An example request/response pair."""

    endpoint_path: str  # Which endpoint this is for
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None  # User-provided context


@dataclass
class MaterialCollection:
    """Collection of materials gathered for integration."""

    requirements_id: str
    collected_at: datetime = field(default_factory=datetime.now)

    # Collected items
    api_docs: List[APIDocumentation] = field(default_factory=list)
    credential_refs: List[CredentialReference] = field(default_factory=list)
    examples: List[APIExample] = field(default_factory=list)
    configurations: Dict[str, Any] = field(default_factory=dict)

    @property
    def collection_complete(self) -> bool:
        """Check if collection has minimum required materials."""
        return len(self.api_docs) > 0 or len(self.examples) > 0

    def add_api_doc(self, doc: APIDocumentation) -> None:
        """Add API documentation to collection."""
        self.api_docs.append(doc)

    def add_credential_ref(self, ref: CredentialReference) -> None:
        """Add credential reference to collection."""
        self.credential_refs.append(ref)

    def add_example(self, example: APIExample) -> None:
        """Add API example to collection."""
        self.examples.append(example)

    def set_configuration(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.configurations[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "requirements_id": self.requirements_id,
            "collected_at": self.collected_at.isoformat(),
            "api_docs": [
                {
                    "source": d.source,
                    "source_type": d.source_type,
                    "base_url": d.base_url,
                    "auth_method": d.auth_method,
                    "endpoints": [
                        {
                            "method": e.method,
                            "path": e.path,
                            "summary": e.summary,
                            "parameters": [
                                {
                                    "name": p.name,
                                    "location": p.location,
                                    "param_type": p.param_type,
                                    "required": p.required,
                                    "description": p.description,
                                }
                                for p in e.parameters
                            ],
                            "request_body": {
                                "content_type": e.request_body.content_type,
                                "schema": e.request_body.schema,
                                "example": e.request_body.example,
                            } if e.request_body else None,
                            "response_schema": {
                                "content_type": e.response_schema.content_type,
                                "schema": e.response_schema.schema,
                                "example": e.response_schema.example,
                            } if e.response_schema else None,
                            "auth_required": e.auth_required,
                            "scopes": e.scopes,
                        }
                        for e in d.endpoints
                    ],
                    "raw_content": d.raw_content,
                }
                for d in self.api_docs
            ],
            "credential_refs": [
                {
                    "name": c.name,
                    "env_var_name": c.env_var_name,
                    "credential_type": c.credential_type,
                    "description": c.description,
                }
                for c in self.credential_refs
            ],
            "examples": [
                {
                    "endpoint_path": e.endpoint_path,
                    "request": e.request,
                    "response": e.response,
                    "notes": e.notes,
                }
                for e in self.examples
            ],
            "configurations": self.configurations,
            "collection_complete": self.collection_complete,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaterialCollection":
        """Deserialize from dictionary."""
        api_docs = []
        for d in data.get("api_docs", []):
            endpoints = []
            for e in d.get("endpoints", []):
                request_body = None
                if e.get("request_body"):
                    request_body = APISchema(
                        content_type=e["request_body"].get("content_type", "application/json"),
                        schema=e["request_body"].get("schema", {}),
                        example=e["request_body"].get("example"),
                    )
                response_schema = None
                if e.get("response_schema"):
                    response_schema = APISchema(
                        content_type=e["response_schema"].get("content_type", "application/json"),
                        schema=e["response_schema"].get("schema", {}),
                        example=e["response_schema"].get("example"),
                    )
                endpoints.append(
                    APIEndpoint(
                        method=e["method"],
                        path=e["path"],
                        summary=e.get("summary"),
                        parameters=[
                            APIParameter(
                                name=p["name"],
                                location=p["location"],
                                param_type=p["param_type"],
                                required=p.get("required", True),
                                description=p.get("description"),
                            )
                            for p in e.get("parameters", [])
                        ],
                        request_body=request_body,
                        response_schema=response_schema,
                        auth_required=e.get("auth_required", True),
                        scopes=e.get("scopes", []),
                    )
                )
            api_docs.append(
                APIDocumentation(
                    source=d["source"],
                    source_type=d["source_type"],
                    base_url=d.get("base_url"),
                    auth_method=d.get("auth_method"),
                    endpoints=endpoints,
                    raw_content=d.get("raw_content"),
                )
            )

        credential_refs = [
            CredentialReference(
                name=c["name"],
                env_var_name=c["env_var_name"],
                credential_type=c["credential_type"],
                description=c["description"],
            )
            for c in data.get("credential_refs", [])
        ]

        examples = [
            APIExample(
                endpoint_path=e["endpoint_path"],
                request=e.get("request", {}),
                response=e.get("response", {}),
                notes=e.get("notes"),
            )
            for e in data.get("examples", [])
        ]

        return cls(
            requirements_id=data["requirements_id"],
            collected_at=datetime.fromisoformat(data["collected_at"]) if "collected_at" in data else datetime.now(),
            api_docs=api_docs,
            credential_refs=credential_refs,
            examples=examples,
            configurations=data.get("configurations", {}),
        )
