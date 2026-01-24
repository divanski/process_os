"""
ProcessOS Material Collector Module

Handles collection of integration materials including:
- API documentation parsing (OpenAPI, Swagger, GraphQL)
- Manual endpoint description
- Example-based schema inference
- Credential reference collection
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .materials import (
    APIDocumentation,
    APIEndpoint,
    APIParameter,
    APISchema,
    CredentialReference,
    MaterialCollection,
)
from .types import (
    Requirements,
)


class MaterialCollector:
    """
    Collects materials needed for integration.

    Handles:
    - OpenAPI/Swagger specification parsing
    - GraphQL schema parsing
    - Manual endpoint description
    - Example-based schema inference
    - Credential reference collection
    """

    def __init__(self, requirements: Optional[Requirements] = None):
        """
        Initialize the MaterialCollector.

        Args:
            requirements: Optional requirements to collect materials for
        """
        self.requirements = requirements
        self._collection: Optional[MaterialCollection] = None

    def start_collection(self) -> MaterialCollection:
        """
        Start a new material collection session.

        Returns:
            MaterialCollection for gathering materials
        """
        req_id = self.requirements.intent_id if self.requirements else "standalone"
        self._collection = MaterialCollection(requirements_id=req_id)
        return self._collection

    def get_collection(self) -> Optional[MaterialCollection]:
        """Get the current collection."""
        return self._collection

    # -------------------------------------------------------------------------
    # OpenAPI/Swagger Parsing
    # -------------------------------------------------------------------------

    def parse_openapi(self, content: str, source: str = "inline") -> APIDocumentation:
        """
        Parse OpenAPI/Swagger specification.

        Args:
            content: JSON or YAML content of the spec
            source: Source identifier (URL, file path, or 'inline')

        Returns:
            Parsed APIDocumentation
        """
        try:
            spec = json.loads(content)
        except json.JSONDecodeError:
            # Try YAML parsing
            try:
                import yaml
                spec = yaml.safe_load(content)
            except ImportError:
                raise ValueError("YAML content requires pyyaml package")
            except Exception as e:
                raise ValueError(f"Failed to parse specification: {e}")

        # Detect spec version
        if "openapi" in spec:
            return self._parse_openapi_3(spec, source)
        elif "swagger" in spec:
            return self._parse_swagger_2(spec, source)
        else:
            raise ValueError("Unknown specification format")

    def _parse_openapi_3(self, spec: Dict[str, Any], source: str) -> APIDocumentation:
        """Parse OpenAPI 3.x specification."""
        # Extract base URL
        base_url = None
        servers = spec.get("servers", [])
        if servers:
            base_url = servers[0].get("url")

        # Extract security/auth method
        auth_method = self._detect_auth_method(spec.get("components", {}).get("securitySchemes", {}))

        # Parse endpoints
        endpoints = []
        for path, path_item in spec.get("paths", {}).items():
            for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
                if method in path_item:
                    operation = path_item[method]
                    endpoint = self._parse_operation(method.upper(), path, operation, spec)
                    endpoints.append(endpoint)

        return APIDocumentation(
            source=source,
            source_type="openapi",
            base_url=base_url,
            auth_method=auth_method,
            endpoints=endpoints,
            raw_content=json.dumps(spec) if len(json.dumps(spec)) < 50000 else None,
        )

    def _parse_swagger_2(self, spec: Dict[str, Any], source: str) -> APIDocumentation:
        """Parse Swagger 2.0 specification."""
        # Build base URL
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        schemes = spec.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"
        base_url = f"{scheme}://{host}{base_path}" if host else None

        # Extract auth method
        auth_method = self._detect_auth_method(spec.get("securityDefinitions", {}))

        # Parse endpoints
        endpoints = []
        for path, path_item in spec.get("paths", {}).items():
            for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
                if method in path_item:
                    operation = path_item[method]
                    endpoint = self._parse_swagger_operation(method.upper(), path, operation)
                    endpoints.append(endpoint)

        return APIDocumentation(
            source=source,
            source_type="swagger",
            base_url=base_url,
            auth_method=auth_method,
            endpoints=endpoints,
            raw_content=json.dumps(spec) if len(json.dumps(spec)) < 50000 else None,
        )

    def _parse_operation(
        self,
        method: str,
        path: str,
        operation: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> APIEndpoint:
        """Parse an OpenAPI 3.x operation into an endpoint."""
        summary = operation.get("summary", operation.get("operationId", ""))

        # Parse parameters
        parameters = []
        for param in operation.get("parameters", []):
            parameters.append(
                APIParameter(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    param_type=self._get_param_type(param),
                    required=param.get("required", False),
                    description=param.get("description"),
                )
            )

        # Parse request body
        request_body = None
        if "requestBody" in operation:
            rb = operation["requestBody"]
            content = rb.get("content", {})
            for content_type, content_schema in content.items():
                schema = content_schema.get("schema", {})
                example = content_schema.get("example")
                request_body = APISchema(
                    content_type=content_type,
                    schema=self._resolve_schema(schema, spec),
                    example=example,
                )
                break  # Use first content type

        # Parse response schema
        response_schema = None
        responses = operation.get("responses", {})
        for status_code in ["200", "201", "default"]:
            if status_code in responses:
                resp = responses[status_code]
                content = resp.get("content", {})
                for content_type, content_schema in content.items():
                    schema = content_schema.get("schema", {})
                    example = content_schema.get("example")
                    response_schema = APISchema(
                        content_type=content_type,
                        schema=self._resolve_schema(schema, spec),
                        example=example,
                    )
                    break
                break

        # Check auth requirement
        auth_required = bool(operation.get("security", spec.get("security", [])))
        scopes = []
        for sec_req in operation.get("security", spec.get("security", [])):
            for sec_name, sec_scopes in sec_req.items():
                scopes.extend(sec_scopes)

        return APIEndpoint(
            method=method,
            path=path,
            summary=summary,
            parameters=parameters,
            request_body=request_body,
            response_schema=response_schema,
            auth_required=auth_required,
            scopes=scopes,
        )

    def _parse_swagger_operation(
        self,
        method: str,
        path: str,
        operation: Dict[str, Any],
    ) -> APIEndpoint:
        """Parse a Swagger 2.0 operation into an endpoint."""
        summary = operation.get("summary", operation.get("operationId", ""))

        # Parse parameters (including body parameter)
        parameters = []
        request_body = None

        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                # Body parameter becomes request body
                schema = param.get("schema", {})
                request_body = APISchema(
                    content_type="application/json",
                    schema=schema,
                    example=param.get("example"),
                )
            else:
                parameters.append(
                    APIParameter(
                        name=param.get("name", ""),
                        location=param.get("in", "query"),
                        param_type=param.get("type", "string"),
                        required=param.get("required", False),
                        description=param.get("description"),
                    )
                )

        return APIEndpoint(
            method=method,
            path=path,
            summary=summary,
            parameters=parameters,
            request_body=request_body,
            response_schema=None,  # Swagger 2.0 responses are more complex
            auth_required=bool(operation.get("security", [])),
            scopes=[],
        )

    def _get_param_type(self, param: Dict[str, Any]) -> str:
        """Extract parameter type from OpenAPI parameter."""
        schema = param.get("schema", {})
        return schema.get("type", param.get("type", "string"))

    def _resolve_schema(self, schema: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve $ref references in schema."""
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/"):
                # Local reference
                parts = ref_path[2:].split("/")
                resolved = spec
                for part in parts:
                    resolved = resolved.get(part, {})
                return resolved
        return schema

    def _detect_auth_method(self, security_schemes: Dict[str, Any]) -> Optional[str]:
        """Detect authentication method from security schemes."""
        for name, scheme in security_schemes.items():
            scheme_type = scheme.get("type", "")
            if scheme_type == "apiKey":
                return "api_key"
            elif scheme_type == "oauth2":
                return "oauth2"
            elif scheme_type == "http":
                auth_scheme = scheme.get("scheme", "")
                if auth_scheme == "bearer":
                    return "bearer"
                elif auth_scheme == "basic":
                    return "basic"
        return None

    # -------------------------------------------------------------------------
    # GraphQL Schema Parsing
    # -------------------------------------------------------------------------

    def parse_graphql(self, schema_content: str, source: str = "inline") -> APIDocumentation:
        """
        Parse GraphQL schema.

        Args:
            schema_content: GraphQL SDL content
            source: Source identifier

        Returns:
            Parsed APIDocumentation (endpoints represent queries/mutations)
        """
        # Basic GraphQL parsing - extract queries and mutations
        endpoints = []

        # Extract Query type operations
        query_match = re.search(r'type\s+Query\s*\{([^}]+)\}', schema_content, re.MULTILINE | re.DOTALL)
        if query_match:
            query_body = query_match.group(1)
            for line in query_body.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    op_match = re.match(r'(\w+)(\([^)]*\))?\s*:\s*(\S+)', line)
                    if op_match:
                        name = op_match.group(1)
                        endpoints.append(
                            APIEndpoint(
                                method="QUERY",
                                path=f"/graphql#{name}",
                                summary=f"Query: {name}",
                            )
                        )

        # Extract Mutation type operations
        mutation_match = re.search(r'type\s+Mutation\s*\{([^}]+)\}', schema_content, re.MULTILINE | re.DOTALL)
        if mutation_match:
            mutation_body = mutation_match.group(1)
            for line in mutation_body.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    op_match = re.match(r'(\w+)(\([^)]*\))?\s*:\s*(\S+)', line)
                    if op_match:
                        name = op_match.group(1)
                        endpoints.append(
                            APIEndpoint(
                                method="MUTATION",
                                path=f"/graphql#{name}",
                                summary=f"Mutation: {name}",
                            )
                        )

        return APIDocumentation(
            source=source,
            source_type="graphql",
            endpoints=endpoints,
            raw_content=schema_content if len(schema_content) < 50000 else None,
        )

    # -------------------------------------------------------------------------
    # Manual Endpoint Creation
    # -------------------------------------------------------------------------

    def create_manual_endpoint(
        self,
        method: str,
        path: str,
        summary: Optional[str] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        request_body: Optional[Dict[str, Any]] = None,
        response: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ) -> APIEndpoint:
        """
        Create an endpoint from manual description.

        Args:
            method: HTTP method
            path: URL path
            summary: Endpoint description
            parameters: List of parameter dicts with name, location, type, required
            request_body: Request body schema dict
            response: Response schema dict
            auth_required: Whether auth is required

        Returns:
            APIEndpoint
        """
        parsed_params = []
        if parameters:
            for p in parameters:
                parsed_params.append(
                    APIParameter(
                        name=p.get("name", ""),
                        location=p.get("location", "query"),
                        param_type=p.get("type", "string"),
                        required=p.get("required", False),
                        description=p.get("description"),
                    )
                )

        request_schema = None
        if request_body:
            schema = self.infer_schema_from_example(request_body)
            request_schema = APISchema(
                content_type="application/json",
                schema=schema,
                example=request_body,
            )

        response_schema = None
        if response:
            schema = self.infer_schema_from_example(response)
            response_schema = APISchema(
                content_type="application/json",
                schema=schema,
                example=response,
            )

        return APIEndpoint(
            method=method.upper(),
            path=path,
            summary=summary or f"{method.upper()} {path}",
            parameters=parsed_params,
            request_body=request_schema,
            response_schema=response_schema,
            auth_required=auth_required,
        )

    def create_manual_api_doc(
        self,
        base_url: str,
        endpoints: List[APIEndpoint],
        auth_method: Optional[str] = None,
    ) -> APIDocumentation:
        """
        Create API documentation from manual endpoints.

        Args:
            base_url: Base URL for the API
            endpoints: List of manually created endpoints
            auth_method: Authentication method

        Returns:
            APIDocumentation
        """
        return APIDocumentation(
            source="manual",
            source_type="manual",
            base_url=base_url,
            auth_method=auth_method,
            endpoints=endpoints,
        )

    # -------------------------------------------------------------------------
    # Example-Based Schema Inference
    # -------------------------------------------------------------------------

    def infer_schema_from_example(self, example: Any) -> Dict[str, Any]:
        """
        Infer JSON Schema from an example value.

        Args:
            example: Example data (dict, list, or primitive)

        Returns:
            JSON Schema dict
        """
        if example is None:
            return {"type": "null"}

        if isinstance(example, bool):
            return {"type": "boolean"}

        if isinstance(example, int):
            return {"type": "integer"}

        if isinstance(example, float):
            return {"type": "number"}

        if isinstance(example, str):
            return {"type": "string"}

        if isinstance(example, list):
            if not example:
                return {"type": "array", "items": {}}
            # Infer from first item
            item_schema = self.infer_schema_from_example(example[0])
            return {"type": "array", "items": item_schema}

        if isinstance(example, dict):
            properties = {}
            for key, value in example.items():
                properties[key] = self.infer_schema_from_example(value)
            return {
                "type": "object",
                "properties": properties,
            }

        return {"type": "string"}  # Fallback

    def create_endpoint_from_examples(
        self,
        method: str,
        path: str,
        request_example: Optional[Dict[str, Any]] = None,
        response_example: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
    ) -> APIEndpoint:
        """
        Create an endpoint from request/response examples.

        Args:
            method: HTTP method
            path: URL path
            request_example: Example request body
            response_example: Example response body
            summary: Endpoint description

        Returns:
            APIEndpoint with inferred schemas
        """
        request_body = None
        if request_example:
            schema = self.infer_schema_from_example(request_example)
            request_body = APISchema(
                content_type="application/json",
                schema=schema,
                example=request_example,
            )

        response_schema = None
        if response_example:
            schema = self.infer_schema_from_example(response_example)
            response_schema = APISchema(
                content_type="application/json",
                schema=schema,
                example=response_example,
            )

        return APIEndpoint(
            method=method.upper(),
            path=path,
            summary=summary or f"{method.upper()} {path}",
            request_body=request_body,
            response_schema=response_schema,
        )

    # -------------------------------------------------------------------------
    # File/URL Loading
    # -------------------------------------------------------------------------

    def load_from_file(self, file_path: str) -> APIDocumentation:
        """
        Load API documentation from a file.

        Args:
            file_path: Path to the specification file

        Returns:
            Parsed APIDocumentation
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text()

        # Detect format from extension
        if path.suffix.lower() in [".graphql", ".gql"]:
            return self.parse_graphql(content, str(path))
        else:
            return self.parse_openapi(content, str(path))

    # -------------------------------------------------------------------------
    # Credential Reference Collection
    # -------------------------------------------------------------------------

    def create_credential_reference(
        self,
        name: str,
        env_var_name: str,
        credential_type: str = "api_key",
        description: str = "",
    ) -> CredentialReference:
        """
        Create a credential reference (env var name only).

        Args:
            name: Human-readable name
            env_var_name: Environment variable name
            credential_type: Type of credential
            description: How the credential is used

        Returns:
            CredentialReference
        """
        return CredentialReference(
            name=name,
            env_var_name=env_var_name,
            credential_type=credential_type,
            description=description,
        )
