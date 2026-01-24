"""
ProcessOS Discovery Patterns Module

Framework-specific pattern detection for models, routes, and services.
Supports Django, Express/Node.js, and Laravel.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from .context import (
    ExistingIntegration,
    LocalModel,
    ModelField,
    ProjectConventions,
    Relationship,
    Route,
    RouteParameter,
    Service,
)


class FrameworkPatterns(ABC):
    """Abstract base class for framework-specific pattern detection."""

    @abstractmethod
    def detect_models(self, content: str, file_path: Path) -> List[LocalModel]:
        """Detect model definitions in the content."""
        pass

    @abstractmethod
    def detect_routes(self, content: str, file_path: Path) -> List[Route]:
        """Detect route definitions in the content."""
        pass

    @abstractmethod
    def detect_services(self, content: str, file_path: Path) -> List[Service]:
        """Detect service class definitions in the content."""
        pass

    def detect_integrations(self, content: str, file_path: Path) -> List[ExistingIntegration]:
        """Detect existing external service integrations."""
        integrations = []

        # Common integration patterns
        integration_patterns = {
            "stripe": (r"stripe|Stripe", "payment"),
            "paypal": (r"paypal|PayPal", "payment"),
            "aws_s3": (r"boto3|s3\.|S3Client|aws.*s3", "storage"),
            "aws_ses": (r"ses\.|SESClient|aws.*ses", "notification"),
            "sendgrid": (r"sendgrid|SendGrid", "notification"),
            "twilio": (r"twilio|Twilio", "notification"),
            "redis": (r"redis|Redis", "cache"),
            "elasticsearch": (r"elasticsearch|Elasticsearch", "search"),
            "mongodb": (r"mongodb|mongoose|MongoClient", "database"),
            "postgresql": (r"psycopg2|pg\.|PostgreSQL", "database"),
        }

        for service_name, (pattern, integration_type) in integration_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                integrations.append(
                    ExistingIntegration(
                        service_name=service_name,
                        integration_type=integration_type,
                        file_paths=[file_path],
                        patterns_used=["direct_api"],
                    )
                )

        return integrations


class DjangoPatterns(FrameworkPatterns):
    """Django-specific pattern detection."""

    def detect_models(self, content: str, file_path: Path) -> List[LocalModel]:
        """Detect Django model classes."""
        models = []

        # Pattern for Django model class definition
        class_pattern = r"class\s+(\w+)\s*\(.*models\.Model.*\):"

        for match in re.finditer(class_pattern, content):
            model_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Find the class body
            class_start = match.end()
            class_body = self._extract_class_body(content, class_start)

            fields = self._extract_django_fields(class_body)
            relationships = self._extract_django_relationships(class_body)
            table_name = self._extract_table_name(class_body, model_name)

            models.append(
                LocalModel(
                    name=model_name,
                    file_path=file_path,
                    line_number=line_number,
                    fields=fields,
                    relationships=relationships,
                    table_name=table_name,
                )
            )

        return models

    def _extract_class_body(self, content: str, start: int) -> str:
        """Extract the body of a class from the start position."""
        lines = content[start:].split("\n")
        body_lines = []
        base_indent = None

        for line in lines[1:]:  # Skip the class line itself
            if not line.strip():
                body_lines.append(line)
                continue

            # Determine indentation
            current_indent = len(line) - len(line.lstrip())
            if base_indent is None and line.strip():
                base_indent = current_indent
                body_lines.append(line)
            elif base_indent is not None:
                if current_indent >= base_indent:
                    body_lines.append(line)
                else:
                    # End of class body
                    break

        return "\n".join(body_lines)

    def _extract_django_fields(self, class_body: str) -> List[ModelField]:
        """Extract Django model fields."""
        fields = []

        # Pattern for Django field definitions
        field_pattern = r"(\w+)\s*=\s*models\.(\w+)Field\s*\("

        for match in re.finditer(field_pattern, class_body):
            field_name = match.group(1)
            field_type = match.group(2).lower()

            # Map Django field types to generic types
            type_mapping = {
                "char": "string",
                "text": "string",
                "integer": "integer",
                "biginteger": "integer",
                "decimal": "decimal",
                "float": "float",
                "boolean": "boolean",
                "datetime": "datetime",
                "date": "date",
                "email": "string",
                "url": "string",
                "uuid": "uuid",
                "json": "json",
            }

            generic_type = type_mapping.get(field_type, field_type)

            # Check for nullable
            nullable = "null=True" in class_body[match.start():match.start() + 200]

            # Check for constraints
            constraints = []
            field_args = class_body[match.end():match.end() + 200]
            if "unique=True" in field_args:
                constraints.append("unique")
            if "db_index=True" in field_args:
                constraints.append("indexed")

            fields.append(
                ModelField(
                    name=field_name,
                    field_type=generic_type,
                    nullable=nullable,
                    constraints=constraints,
                )
            )

        return fields

    def _extract_django_relationships(self, class_body: str) -> List[Relationship]:
        """Extract Django model relationships."""
        relationships = []

        # ForeignKey pattern
        fk_pattern = r"(\w+)\s*=\s*models\.ForeignKey\s*\(\s*['\"]?(\w+)['\"]?"
        for match in re.finditer(fk_pattern, class_body):
            field_name = match.group(1)
            target_model = match.group(2)

            # Extract related_name if present
            related_name = None
            related_pattern = r"related_name\s*=\s*['\"](\w+)['\"]"
            related_match = re.search(related_pattern, class_body[match.start():match.start() + 300])
            if related_match:
                related_name = related_match.group(1)

            relationships.append(
                Relationship(
                    type="foreign_key",
                    target_model=target_model,
                    field_name=field_name,
                    reverse_name=related_name,
                )
            )

        # ManyToManyField pattern
        m2m_pattern = r"(\w+)\s*=\s*models\.ManyToManyField\s*\(\s*['\"]?(\w+)['\"]?"
        for match in re.finditer(m2m_pattern, class_body):
            field_name = match.group(1)
            target_model = match.group(2)

            relationships.append(
                Relationship(
                    type="many_to_many",
                    target_model=target_model,
                    field_name=field_name,
                )
            )

        # OneToOneField pattern
        o2o_pattern = r"(\w+)\s*=\s*models\.OneToOneField\s*\(\s*['\"]?(\w+)['\"]?"
        for match in re.finditer(o2o_pattern, class_body):
            field_name = match.group(1)
            target_model = match.group(2)

            relationships.append(
                Relationship(
                    type="one_to_one",
                    target_model=target_model,
                    field_name=field_name,
                )
            )

        return relationships

    def _extract_table_name(self, class_body: str, model_name: str) -> str:
        """Extract Django model table name."""
        # Check for explicit db_table in Meta class
        meta_pattern = r"class\s+Meta\s*:.*?db_table\s*=\s*['\"](\w+)['\"]"
        match = re.search(meta_pattern, class_body, re.DOTALL)
        if match:
            return match.group(1)

        # Default Django table naming: app_modelname (lowercase)
        return model_name.lower() + "s"

    def detect_routes(self, content: str, file_path: Path) -> List[Route]:
        """Detect Django URL patterns."""
        routes = []

        # Pattern for path() definitions
        path_pattern = r"path\s*\(\s*['\"]([^'\"]+)['\"].*?(?:views\.)?(\w+)"

        for match in re.finditer(path_pattern, content):
            url_path = match.group(1)
            handler = match.group(2)
            line_number = content[:match.start()].count("\n") + 1

            # Determine HTTP method from handler name or view type
            method = self._infer_http_method(handler, content)

            # Extract path parameters
            parameters = self._extract_path_parameters(url_path)

            routes.append(
                Route(
                    method=method,
                    path=f"/{url_path}" if not url_path.startswith("/") else url_path,
                    handler=handler,
                    file_path=file_path,
                    line_number=line_number,
                    parameters=parameters,
                )
            )

        return routes

    def _infer_http_method(self, handler: str, content: str) -> str:
        """Infer HTTP method from handler name or view definition."""
        handler_lower = handler.lower()

        # Check for explicit method decorators in content
        if f"def {handler}" in content or f"class {handler}" in content:
            # Look for require_http_methods decorator
            method_pattern = r"@require_http_methods\s*\(\s*\[['\"](\w+)['\"]"
            match = re.search(method_pattern, content)
            if match:
                return match.group(1).upper()

        # Infer from common naming patterns
        if "create" in handler_lower or "store" in handler_lower:
            return "POST"
        elif "update" in handler_lower or "edit" in handler_lower:
            return "PUT"
        elif "delete" in handler_lower or "destroy" in handler_lower:
            return "DELETE"
        elif "list" in handler_lower or "index" in handler_lower:
            return "GET"

        # Default to GET for views
        return "GET"

    def _extract_path_parameters(self, url_path: str) -> List[RouteParameter]:
        """Extract parameters from Django URL path."""
        parameters = []

        # Django path converter syntax: <type:name> or <name>
        param_pattern = r"<(?:(\w+):)?(\w+)>"

        for match in re.finditer(param_pattern, url_path):
            param_type = match.group(1) or "str"
            param_name = match.group(2)

            type_mapping = {
                "int": "integer",
                "str": "string",
                "slug": "string",
                "uuid": "uuid",
                "path": "string",
            }

            parameters.append(
                RouteParameter(
                    name=param_name,
                    location="path",
                    param_type=type_mapping.get(param_type, "string"),
                    required=True,
                )
            )

        return parameters

    def detect_services(self, content: str, file_path: Path) -> List[Service]:
        """Detect Django service classes."""
        services = []

        # Pattern for service class definitions
        class_pattern = r"class\s+(\w+(?:Service|Manager|Repository|Handler))\s*(?:\([^)]*\))?\s*:"

        for match in re.finditer(class_pattern, content):
            service_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Extract the class body
            class_start = match.end()
            class_body = self._extract_class_body(content, class_start)

            # Extract methods
            methods = self._extract_methods(class_body)

            # Extract dependencies from __init__
            dependencies = self._extract_dependencies(class_body)

            services.append(
                Service(
                    name=service_name,
                    file_path=file_path,
                    line_number=line_number,
                    service_type="class",
                    methods=methods,
                    dependencies=dependencies,
                )
            )

        return services

    def _extract_methods(self, class_body: str) -> List[str]:
        """Extract public method names from class body."""
        methods = []
        method_pattern = r"def\s+([a-z_]\w*)\s*\("

        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            # Skip private methods and dunder methods
            if not method_name.startswith("_"):
                methods.append(method_name)

        return methods

    def _extract_dependencies(self, class_body: str) -> List[str]:
        """Extract dependency types from __init__ method."""
        dependencies = []

        # Look for __init__ with type-annotated parameters
        init_pattern = r"def\s+__init__\s*\([^)]+\)"
        init_match = re.search(init_pattern, class_body)

        if init_match:
            init_def = init_match.group(0)
            # Extract type annotations
            type_pattern = r"(\w+)\s*:\s*(\w+)"
            for param_match in re.finditer(type_pattern, init_def):
                param_type = param_match.group(2)
                if param_type not in ("str", "int", "bool", "float", "list", "dict", "None", "self"):
                    dependencies.append(param_type)

        return dependencies


class ExpressPatterns(FrameworkPatterns):
    """Express/Node.js-specific pattern detection."""

    def detect_models(self, content: str, file_path: Path) -> List[LocalModel]:
        """Detect Mongoose model schemas."""
        models = []

        # Pattern for Mongoose schema and model export
        schema_pattern = r"const\s+(\w+)Schema\s*=\s*new\s+mongoose\.Schema\s*\("
        model_pattern = r"module\.exports\s*=\s*mongoose\.model\s*\(\s*['\"](\w+)['\"]"

        # Find schema definitions
        for match in re.finditer(schema_pattern, content):
            schema_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Extract schema definition
            schema_start = match.end()
            schema_body = self._extract_object_body(content, schema_start)

            fields = self._extract_mongoose_fields(schema_body)
            relationships = self._extract_mongoose_relationships(schema_body)

            # Get actual model name from export
            model_name = schema_name  # Default
            model_match = re.search(model_pattern, content)
            if model_match:
                model_name = model_match.group(1)

            models.append(
                LocalModel(
                    name=model_name,
                    file_path=file_path,
                    line_number=line_number,
                    fields=fields,
                    relationships=relationships,
                )
            )

        return models

    def _extract_object_body(self, content: str, start: int) -> str:
        """Extract JavaScript object body from start position."""
        depth = 0
        body_start = None
        for i, char in enumerate(content[start:]):
            if char == "{":
                if depth == 0:
                    body_start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start + body_start:start + i + 1]
        return content[start:start + 1000]

    def _extract_mongoose_fields(self, schema_body: str) -> List[ModelField]:
        """Extract Mongoose schema fields."""
        fields = []

        # Pattern for field definitions
        field_pattern = r"(\w+)\s*:\s*(?:\{\s*type\s*:\s*(\w+)|(\w+))"

        for match in re.finditer(field_pattern, schema_body):
            field_name = match.group(1)
            field_type = match.group(2) or match.group(3)

            if field_type:
                type_mapping = {
                    "String": "string",
                    "Number": "number",
                    "Boolean": "boolean",
                    "Date": "datetime",
                    "ObjectId": "uuid",
                    "Buffer": "binary",
                    "Mixed": "json",
                    "Array": "array",
                }

                generic_type = type_mapping.get(field_type, field_type.lower())

                # Check for required
                required = "required: true" in schema_body or "required: [true" in schema_body

                # Check for unique
                constraints = []
                if "unique: true" in schema_body:
                    constraints.append("unique")
                if "index: true" in schema_body:
                    constraints.append("indexed")

                fields.append(
                    ModelField(
                        name=field_name,
                        field_type=generic_type,
                        nullable=not required,
                        constraints=constraints,
                    )
                )

        return fields

    def _extract_mongoose_relationships(self, schema_body: str) -> List[Relationship]:
        """Extract Mongoose references."""
        relationships = []

        # Pattern for ref definitions
        ref_pattern = r"(\w+)\s*:\s*\{[^}]*ref\s*:\s*['\"](\w+)['\"]"

        for match in re.finditer(ref_pattern, schema_body):
            field_name = match.group(1)
            target_model = match.group(2)

            relationships.append(
                Relationship(
                    type="foreign_key",
                    target_model=target_model,
                    field_name=field_name,
                )
            )

        return relationships

    def detect_routes(self, content: str, file_path: Path) -> List[Route]:
        """Detect Express route handlers."""
        routes = []

        # Pattern for router.method() calls
        route_pattern = r"router\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"

        for match in re.finditer(route_pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)
            line_number = content[:match.start()].count("\n") + 1

            # Extract path parameters
            parameters = self._extract_express_parameters(path)

            routes.append(
                Route(
                    method=method,
                    path=path,
                    handler=f"{method.lower()}_{path.replace('/', '_').strip('_')}",
                    file_path=file_path,
                    line_number=line_number,
                    parameters=parameters,
                )
            )

        return routes

    def _extract_express_parameters(self, path: str) -> List[RouteParameter]:
        """Extract Express route parameters."""
        parameters = []

        # Express param syntax: :paramName
        param_pattern = r":(\w+)"

        for match in re.finditer(param_pattern, path):
            param_name = match.group(1)
            parameters.append(
                RouteParameter(
                    name=param_name,
                    location="path",
                    param_type="string",
                    required=True,
                )
            )

        return parameters

    def detect_services(self, content: str, file_path: Path) -> List[Service]:
        """Detect Express service classes."""
        services = []

        # Pattern for class definitions
        class_pattern = r"class\s+(\w+(?:Service|Manager|Repository|Handler))\s*(?:extends\s+\w+)?\s*\{"

        for match in re.finditer(class_pattern, content):
            service_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Extract methods
            class_body = self._extract_object_body(content, match.start())
            methods = self._extract_js_methods(class_body)

            services.append(
                Service(
                    name=service_name,
                    file_path=file_path,
                    line_number=line_number,
                    service_type="class",
                    methods=methods,
                    dependencies=[],
                )
            )

        return services

    def _extract_js_methods(self, class_body: str) -> List[str]:
        """Extract JavaScript method names from class body."""
        methods = []

        # Method pattern: async? methodName(
        method_pattern = r"(?:async\s+)?([a-z]\w*)\s*\("

        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            # Skip constructor and private
            if method_name != "constructor" and not method_name.startswith("_"):
                methods.append(method_name)

        return list(set(methods))  # Deduplicate


class LaravelPatterns(FrameworkPatterns):
    """Laravel-specific pattern detection."""

    def detect_models(self, content: str, file_path: Path) -> List[LocalModel]:
        """Detect Laravel Eloquent models."""
        models = []

        # Pattern for Eloquent model class definition
        class_pattern = r"class\s+(\w+)\s+extends\s+Model"

        for match in re.finditer(class_pattern, content):
            model_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Extract class body
            class_start = match.end()
            class_body = self._extract_php_class_body(content, class_start)

            fields = self._extract_laravel_fields(class_body)
            relationships = self._extract_laravel_relationships(class_body)
            table_name = self._extract_laravel_table_name(class_body, model_name)

            models.append(
                LocalModel(
                    name=model_name,
                    file_path=file_path,
                    line_number=line_number,
                    fields=fields,
                    relationships=relationships,
                    table_name=table_name,
                )
            )

        return models

    def _extract_php_class_body(self, content: str, start: int) -> str:
        """Extract PHP class body from start position."""
        depth = 0
        body_start = None
        for i, char in enumerate(content[start:]):
            if char == "{":
                if depth == 0:
                    body_start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start + body_start:start + i + 1]
        return content[start:start + 2000]

    def _extract_laravel_fields(self, class_body: str) -> List[ModelField]:
        """Extract Laravel model fields from $fillable or $casts."""
        fields = []

        # Extract from $fillable array
        fillable_pattern = r"\$fillable\s*=\s*\[(.*?)\]"
        fillable_match = re.search(fillable_pattern, class_body, re.DOTALL)

        if fillable_match:
            fillable_content = fillable_match.group(1)
            field_names = re.findall(r"['\"](\w+)['\"]", fillable_content)

            for name in field_names:
                fields.append(
                    ModelField(
                        name=name,
                        field_type="string",  # Default, can be refined from $casts
                        nullable=True,
                    )
                )

        # Refine types from $casts
        casts_pattern = r"\$casts\s*=\s*\[(.*?)\]"
        casts_match = re.search(casts_pattern, class_body, re.DOTALL)

        if casts_match:
            casts_content = casts_match.group(1)
            cast_entries = re.findall(r"['\"](\w+)['\"]\s*=>\s*['\"](\w+)['\"]", casts_content)

            type_mapping = {
                "boolean": "boolean",
                "integer": "integer",
                "float": "float",
                "double": "float",
                "string": "string",
                "array": "array",
                "json": "json",
                "object": "json",
                "collection": "array",
                "date": "date",
                "datetime": "datetime",
                "timestamp": "datetime",
                "decimal": "decimal",
            }

            for field_name, cast_type in cast_entries:
                # Update existing field type or add new field
                existing_field = next((f for f in fields if f.name == field_name), None)
                if existing_field:
                    existing_field.field_type = type_mapping.get(cast_type.lower(), cast_type)
                else:
                    fields.append(
                        ModelField(
                            name=field_name,
                            field_type=type_mapping.get(cast_type.lower(), cast_type),
                            nullable=True,
                        )
                    )

        return fields

    def _extract_laravel_relationships(self, class_body: str) -> List[Relationship]:
        """Extract Laravel Eloquent relationships."""
        relationships = []

        # Relationship method patterns
        relationship_patterns = [
            (r"function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*return\s+\$this->hasMany\s*\(\s*(\w+)::class", "one_to_many"),
            (r"function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*return\s+\$this->belongsTo\s*\(\s*(\w+)::class", "foreign_key"),
            (r"function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*return\s+\$this->hasOne\s*\(\s*(\w+)::class", "one_to_one"),
            (r"function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*return\s+\$this->belongsToMany\s*\(\s*(\w+)::class", "many_to_many"),
        ]

        for pattern, rel_type in relationship_patterns:
            for match in re.finditer(pattern, class_body):
                field_name = match.group(1)
                target_model = match.group(2)

                relationships.append(
                    Relationship(
                        type=rel_type,
                        target_model=target_model,
                        field_name=field_name,
                    )
                )

        return relationships

    def _extract_laravel_table_name(self, class_body: str, model_name: str) -> str:
        """Extract Laravel model table name."""
        # Check for explicit $table property
        table_pattern = r"\$table\s*=\s*['\"](\w+)['\"]"
        match = re.search(table_pattern, class_body)
        if match:
            return match.group(1)

        # Default Laravel table naming: snake_case plural
        import re as regex
        # Convert PascalCase to snake_case and pluralize
        snake_name = regex.sub(r"(?<!^)(?=[A-Z])", "_", model_name).lower()
        return snake_name + "s"

    def detect_routes(self, content: str, file_path: Path) -> List[Route]:
        """Detect Laravel route definitions."""
        routes = []

        # Pattern for Route:: method calls
        route_pattern = r"Route::(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"].*?\[([^]]+)\]"

        for match in re.finditer(route_pattern, content, re.DOTALL):
            method = match.group(1).upper()
            path = match.group(2)
            controller_action = match.group(3)
            line_number = content[:match.start()].count("\n") + 1

            # Extract controller and method
            handler_match = re.search(r"(\w+)::class\s*,\s*['\"](\w+)['\"]", controller_action)
            if handler_match:
                controller = handler_match.group(1)
                action = handler_match.group(2)
                handler = f"{controller}@{action}"
            else:
                handler = controller_action.strip()

            # Extract parameters
            parameters = self._extract_laravel_parameters(path)

            routes.append(
                Route(
                    method=method,
                    path=f"/{path}" if not path.startswith("/") else path,
                    handler=handler,
                    file_path=file_path,
                    line_number=line_number,
                    parameters=parameters,
                )
            )

        return routes

    def _extract_laravel_parameters(self, path: str) -> List[RouteParameter]:
        """Extract Laravel route parameters."""
        parameters = []

        # Laravel param syntax: {paramName} or {paramName?}
        param_pattern = r"\{(\w+)\??}"

        for match in re.finditer(param_pattern, path):
            param_name = match.group(1)
            is_optional = match.group(0).endswith("?}")

            parameters.append(
                RouteParameter(
                    name=param_name,
                    location="path",
                    param_type="string",
                    required=not is_optional,
                )
            )

        return parameters

    def detect_services(self, content: str, file_path: Path) -> List[Service]:
        """Detect Laravel service classes."""
        services = []

        # Pattern for service class definitions
        class_pattern = r"class\s+(\w+(?:Service|Repository|Manager|Handler))\s*(?:extends\s+\w+)?\s*\{"

        for match in re.finditer(class_pattern, content):
            service_name = match.group(1)
            line_number = content[:match.start()].count("\n") + 1

            # Extract class body
            class_body = self._extract_php_class_body(content, match.start())

            methods = self._extract_php_methods(class_body)
            dependencies = self._extract_php_dependencies(class_body)

            services.append(
                Service(
                    name=service_name,
                    file_path=file_path,
                    line_number=line_number,
                    service_type="class",
                    methods=methods,
                    dependencies=dependencies,
                )
            )

        return services

    def _extract_php_methods(self, class_body: str) -> List[str]:
        """Extract PHP public method names."""
        methods = []

        method_pattern = r"public\s+function\s+(\w+)\s*\("

        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            if method_name != "__construct":
                methods.append(method_name)

        return methods

    def _extract_php_dependencies(self, class_body: str) -> List[str]:
        """Extract PHP constructor dependencies."""
        dependencies = []

        # Look for constructor with type-hinted parameters
        constructor_pattern = r"public\s+function\s+__construct\s*\(([^)]+)\)"
        match = re.search(constructor_pattern, class_body)

        if match:
            params = match.group(1)
            # Extract type hints
            type_pattern = r"(\w+)\s+\$\w+"
            for type_match in re.finditer(type_pattern, params):
                param_type = type_match.group(1)
                if param_type not in ("string", "int", "bool", "float", "array"):
                    dependencies.append(param_type)

        return dependencies


def get_patterns_for_framework(framework: str) -> Optional[FrameworkPatterns]:
    """Get the appropriate pattern detector for a framework."""
    framework_map = {
        "django": DjangoPatterns,
        "express": ExpressPatterns,
        "node": ExpressPatterns,
        "laravel": LaravelPatterns,
        "php": LaravelPatterns,
    }
    pattern_class = framework_map.get(framework.lower())
    return pattern_class() if pattern_class else None


def infer_conventions(code: str, language: str) -> ProjectConventions:
    """Infer coding conventions from code sample."""
    conventions = ProjectConventions()

    # Detect class naming
    class_names = re.findall(r"class\s+(\w+)", code)
    if class_names:
        if all(name[0].isupper() and "_" not in name for name in class_names):
            conventions.class_naming = "PascalCase"
        elif all("_" in name for name in class_names):
            conventions.class_naming = "snake_case"

    # Detect function naming
    if language == "python":
        func_names = re.findall(r"def\s+([a-z_]\w*)\s*\(", code)
        if func_names:
            if all("_" in name for name in func_names if len(name) > 3):
                conventions.function_naming = "snake_case"
    elif language in ("javascript", "typescript"):
        func_names = re.findall(r"(?:function|async)\s+([a-z]\w*)\s*\(", code)
        method_names = re.findall(r"([a-z]\w*)\s*\([^)]*\)\s*\{", code)
        all_funcs = func_names + method_names
        if all_funcs:
            if any(name[0].islower() and any(c.isupper() for c in name) for name in all_funcs):
                conventions.function_naming = "camelCase"

    # Detect type hints (Python)
    if language == "python":
        conventions.type_hints = bool(re.search(r":\s*\w+\s*[=)]|-> \w+", code))

    # Detect service pattern
    if re.search(r"class\s+\w+Service", code):
        conventions.service_pattern = "service_classes"
        # Check for dependency injection
        if re.search(r"def\s+__init__\s*\([^)]*:\s*\w+", code):
            conventions.dependency_injection = True

    # Detect docstring style (Python)
    if language == "python":
        if re.search(r'""".*Args:', code, re.DOTALL):
            conventions.docstring_style = "google"
        elif re.search(r'""".*Parameters\s*-+', code, re.DOTALL):
            conventions.docstring_style = "numpy"
        elif re.search(r'""".*:param\s+\w+:', code, re.DOTALL):
            conventions.docstring_style = "sphinx"

    return conventions
