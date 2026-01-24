"""
Pattern extractor for extracting component details from source files.

This module analyzes source files to extract:
- Component types (adapter, service, interface, contract)
- File patterns and naming conventions
- Namespaces and directory structures
- Interface implementations and method signatures
- Relationships between components
"""

import re
from pathlib import Path
from typing import Optional

from process_os.architecture import (
    ProgrammingLanguage,
    ProjectArchitecture,
)

from process_os.patterns.types import (
    RelationshipType,
    PatternComponent,
    ComponentRelationship,
    MethodSignature,
    ParameterInfo,
)


class PatternExtractor:
    """Extracts pattern details from source files.

    Analyzes source files to identify:
    - Component types (adapter, service, interface)
    - File patterns ({Name}Adapter.php)
    - Namespaces
    - Interface implementations
    - Required methods
    - Relationships between components
    """

    # Common component type indicators
    COMPONENT_INDICATORS = {
        "adapter": ["Adapter", "Gateway", "Client", "Driver"],
        "service": ["Service", "Manager", "Handler"],
        "interface": ["Interface", "Contract"],
        "repository": ["Repository", "Store"],
        "factory": ["Factory", "Builder"],
        "controller": ["Controller"],
    }

    def __init__(self):
        """Initialize the pattern extractor."""
        self._php_namespace_pattern = re.compile(r"namespace\s+([\w\\]+);")
        self._php_class_pattern = re.compile(
            r"class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\\,\s]+))?"
        )
        self._php_interface_pattern = re.compile(r"interface\s+(\w+)")
        self._php_method_pattern = re.compile(
            r"(public|protected|private)?\s*(static)?\s*function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?"
        )
        self._php_use_pattern = re.compile(r"use\s+([\w\\]+)(?:\s+as\s+(\w+))?;")

    def extract_components(
        self, file_paths: list[Path], language: ProgrammingLanguage
    ) -> list[PatternComponent]:
        """Extract components from a list of files.

        Args:
            file_paths: List of source files to analyze
            language: Programming language of the files

        Returns:
            List of PatternComponent objects describing each component
        """
        components = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            component = self._extract_component_from_file(file_path, language)
            if component:
                components.append(component)

        return components

    def extract_registration_patterns(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> dict:
        """Extract registration/binding patterns from a file.

        Detects how components are registered in the framework:
        - Service provider bindings (Laravel)
        - Configuration arrays
        - Dependency injection patterns

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            Dict with registration details
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return {}

        registrations = {
            "service_providers": [],
            "bindings": [],
            "config_files": [],
            "route_files": [],
        }

        if language == ProgrammingLanguage.PHP:
            # Detect service provider registration
            if "ServiceProvider" in content:
                registrations["service_providers"].append(file_path)

            # Detect $this->app->bind() patterns
            bind_pattern = re.compile(r"\$this->app->bind\(['\"]([^'\"]+)['\"],\s*([^)]+)\)")
            bindings = bind_pattern.findall(content)
            registrations["bindings"].extend(bindings)

            # Detect config() function calls
            config_pattern = re.compile(r"config\(['\"]([^'\"]+)['\"]\)")
            configs = config_pattern.findall(content)
            registrations["config_files"].extend(configs)

            # Detect Route:: usage
            if "Route::" in content:
                registrations["route_files"].append(file_path)

        elif language == ProgrammingLanguage.PYTHON:
            # Detect Django app registration
            if "AppConfig" in content or "apps.py" in str(file_path):
                registrations["service_providers"].append(file_path)

        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            # Detect Express app.use() or app.get() patterns
            if "app.use(" in content or "app.get(" in content:
                registrations["route_files"].append(file_path)

        return registrations

    def extract_config_file_patterns(
        self, project_path: Path, language: ProgrammingLanguage
    ) -> dict:
        """Extract configuration file patterns from project.

        Finds and analyzes config files (config.php, settings.py, etc.).

        Args:
            project_path: Root path of project
            language: Programming language

        Returns:
            Dict mapping config type to list of config files
        """
        config_patterns = {
            "php": ["config/*.php"],
            "python": ["settings.py", "**/settings.py", "**/config.py"],
            "javascript": ["config.js", "config/*.js", ".env*"],
        }

        extensions = {
            "php": ".php",
            "python": ".py",
            "javascript": ".js",
        }

        lang_key = "python" if language == ProgrammingLanguage.PYTHON else "php"
        if language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            lang_key = "javascript"

        configs = {
            "files": [],
            "patterns": config_patterns.get(lang_key, []),
        }

        if project_path.exists():
            # Search for common config file names
            for file_path in project_path.rglob("*"):
                if not file_path.is_file():
                    continue

                name = file_path.name.lower()
                parent_name = file_path.parent.name.lower()

                # Check for config files
                if name in ["config.php", "config.py", "config.js", ".env", ".env.local"]:
                    configs["files"].append(file_path)
                elif parent_name == "config" and file_path.suffix in [".php", ".py", ".js"]:
                    configs["files"].append(file_path)

        return configs

    def extract_relationships(
        self, components: list[PatternComponent], architecture: ProjectArchitecture
    ) -> list[ComponentRelationship]:
        """Extract relationships between components.

        Analyzes components to find:
        - IMPLEMENTS: Adapter implements Interface
        - USES: Service uses Adapter
        - EXTENDS: Class extends BaseClass

        Args:
            components: List of components to analyze
            architecture: Project architecture for context

        Returns:
            List of ComponentRelationship objects
        """
        relationships = []

        # Build maps for efficient lookup
        components_by_type = {}
        for c in components:
            if c.component_type not in components_by_type:
                components_by_type[c.component_type] = []
            components_by_type[c.component_type].append(c)

        # Check for IMPLEMENTS relationships
        adapters = components_by_type.get("adapter", [])
        interfaces = components_by_type.get("interface", [])

        if adapters and interfaces:
            # If we have adapters and interfaces, assume adapters implement interfaces
            for adapter in adapters:
                if adapter.interfaces:
                    relationships.append(
                        ComponentRelationship(
                            source="adapter",
                            target="interface",
                            relationship_type=RelationshipType.IMPLEMENTS,
                            description="Adapter implements interface",
                        )
                    )

        # Check for USES relationships (service uses adapter)
        services = components_by_type.get("service", [])
        if adapters and services:
            for service in services:
                # Service uses adapter
                relationships.append(
                    ComponentRelationship(
                        source="service",
                        target="adapter",
                        relationship_type=RelationshipType.USES,
                        description="Service uses Adapter",
                    )
                )

        return relationships

    def _extract_component_from_file(
        self, file_path: Path, language: ProgrammingLanguage
    ) -> Optional[PatternComponent]:
        """Extract component information from a single file.

        Args:
            file_path: Path to the source file
            language: Programming language

        Returns:
            PatternComponent or None if not a valid component
        """
        if language == ProgrammingLanguage.PHP:
            return self._extract_php_component(file_path)
        elif language == ProgrammingLanguage.PYTHON:
            return self._extract_python_component(file_path)
        elif language in (ProgrammingLanguage.JAVASCRIPT, ProgrammingLanguage.TYPESCRIPT):
            return self._extract_js_component(file_path)

        return None

    def _extract_php_component(self, file_path: Path) -> Optional[PatternComponent]:
        """Extract component from a PHP file.

        Args:
            file_path: Path to PHP file

        Returns:
            PatternComponent or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return None

        # Extract namespace
        namespace = ""
        namespace_match = self._php_namespace_pattern.search(content)
        if namespace_match:
            namespace = namespace_match.group(1)

        # Determine component type and class name
        component_type = None
        class_name = None
        base_class = None
        interfaces = []
        required_methods = []

        # Check for interface
        interface_match = self._php_interface_pattern.search(content)
        if interface_match:
            class_name = interface_match.group(1)
            component_type = "interface"
            # Extract methods from interface
            required_methods = self._extract_php_methods(content, is_interface=True)
        else:
            # Check for class
            class_match = self._php_class_pattern.search(content)
            if class_match:
                class_name = class_match.group(1)
                base_class = class_match.group(2)
                implements_str = class_match.group(3)

                if implements_str:
                    interfaces = [
                        i.strip().split("\\")[-1]
                        for i in implements_str.split(",")
                    ]

                # Determine component type from class name
                component_type = self._determine_component_type(class_name)

        if not class_name or not component_type:
            return None

        # Generate file pattern
        file_pattern = self._generate_file_pattern(class_name, file_path.suffix)

        return PatternComponent(
            component_type=component_type,
            file_pattern=file_pattern,
            directory=str(file_path.parent.relative_to(file_path.parent.parent.parent.parent)),
            namespace=namespace,
            base_class=base_class,
            interfaces=interfaces,
            required_methods=required_methods,
            examples=[file_path],
        )

    def _extract_python_component(self, file_path: Path) -> Optional[PatternComponent]:
        """Extract component from a Python file.

        Args:
            file_path: Path to Python file

        Returns:
            PatternComponent or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return None

        # Extract class definition
        class_pattern = re.compile(r"class\s+(\w+)(?:\(([^)]+)\))?:")
        class_match = class_pattern.search(content)

        if not class_match:
            return None

        class_name = class_match.group(1)
        bases_str = class_match.group(2)

        base_class = None
        interfaces = []
        if bases_str:
            bases = [b.strip() for b in bases_str.split(",")]
            for base in bases:
                if "ABC" in base or "Interface" in base or "Protocol" in base:
                    interfaces.append(base)
                elif not base_class:
                    base_class = base

        component_type = self._determine_component_type(class_name)

        if not component_type:
            return None

        file_pattern = self._generate_file_pattern(class_name, file_path.suffix)

        # Get module path for namespace
        namespace = file_path.stem  # Simplified for Python

        return PatternComponent(
            component_type=component_type,
            file_pattern=file_pattern,
            directory=str(file_path.parent),
            namespace=namespace,
            base_class=base_class,
            interfaces=interfaces,
            examples=[file_path],
        )

    def _extract_js_component(self, file_path: Path) -> Optional[PatternComponent]:
        """Extract component from a JavaScript/TypeScript file.

        Args:
            file_path: Path to JS/TS file

        Returns:
            PatternComponent or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return None

        # Look for class exports
        class_pattern = re.compile(r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?")
        class_match = class_pattern.search(content)

        if not class_match:
            return None

        class_name = class_match.group(1)
        base_class = class_match.group(2)
        implements_str = class_match.group(3)

        interfaces = []
        if implements_str:
            interfaces = [i.strip() for i in implements_str.split(",")]

        component_type = self._determine_component_type(class_name)

        if not component_type:
            return None

        file_pattern = self._generate_file_pattern(class_name, file_path.suffix)

        return PatternComponent(
            component_type=component_type,
            file_pattern=file_pattern,
            directory=str(file_path.parent),
            namespace="",
            base_class=base_class,
            interfaces=interfaces,
            examples=[file_path],
        )

    def _extract_php_methods(
        self, content: str, is_interface: bool = False
    ) -> list[MethodSignature]:
        """Extract method signatures from PHP content.

        Args:
            content: PHP file content
            is_interface: Whether this is an interface (all methods are abstract)

        Returns:
            List of MethodSignature objects
        """
        methods = []

        for match in self._php_method_pattern.finditer(content):
            visibility = match.group(1) or "public"
            is_static = match.group(2) is not None
            name = match.group(3)
            params_str = match.group(4)
            return_type = match.group(5)

            # Skip constructor and magic methods
            if name.startswith("__"):
                continue

            parameters = self._parse_php_parameters(params_str)

            methods.append(
                MethodSignature(
                    name=name,
                    parameters=parameters,
                    return_type=return_type,
                    visibility=visibility,
                    is_abstract=is_interface,
                    is_static=is_static,
                )
            )

        return methods

    def _parse_php_parameters(self, params_str: str) -> list[ParameterInfo]:
        """Parse PHP parameter string into ParameterInfo list.

        Args:
            params_str: Raw parameter string from method signature

        Returns:
            List of ParameterInfo objects
        """
        if not params_str.strip():
            return []

        parameters = []
        param_pattern = re.compile(r"(?:(\??\w+)\s+)?(\$\w+)(?:\s*=\s*(.+))?")

        for param in params_str.split(","):
            param = param.strip()
            match = param_pattern.match(param)
            if match:
                type_hint = match.group(1)
                name = match.group(2).lstrip("$")
                default = match.group(3)

                parameters.append(
                    ParameterInfo(
                        name=name,
                        type_hint=type_hint,
                        default_value=default,
                        is_optional=default is not None or (type_hint and type_hint.startswith("?")),
                    )
                )

        return parameters

    def _determine_component_type(self, class_name: str) -> Optional[str]:
        """Determine component type from class name.

        Args:
            class_name: Name of the class

        Returns:
            Component type string or None
        """
        for comp_type, indicators in self.COMPONENT_INDICATORS.items():
            for indicator in indicators:
                if indicator in class_name:
                    return comp_type

        return None

    def _generate_file_pattern(self, class_name: str, suffix: str) -> str:
        """Generate a file pattern from class name.

        Replaces the variable part (e.g., DHL in DHLAdapter) with {Name}.

        Args:
            class_name: Name of the class
            suffix: File extension (.php, .py, etc.)

        Returns:
            File pattern string like {Name}Adapter.php
        """
        # Check for common suffixes in order of specificity (longest first)
        suffixes = []
        for comp_type, indicators in self.COMPONENT_INDICATORS.items():
            for indicator in indicators:
                suffixes.append((indicator, len(indicator)))

        # Sort by length descending (longest first) to match longest suffix
        suffixes.sort(key=lambda x: x[1], reverse=True)

        for suffix_str, _ in suffixes:
            if class_name.endswith(suffix_str):
                # Replace the prefix with {Name}
                prefix = class_name[: -len(suffix_str)]
                if prefix:
                    return f"{{Name}}{suffix_str}{suffix}"
                else:
                    return f"{suffix_str}{suffix}"

        # If no pattern found, return the class name as pattern
        return f"{class_name}{suffix}"
