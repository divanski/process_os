"""
Template engine for code generation.

Renders integration point templates for different frameworks and languages.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from process_os.architecture import ProjectArchitecture, FrameworkType, ProgrammingLanguage
from process_os.conventions import CodeConventions


class TemplateEngine:
    """Template engine for generating integration point code.
    
    Handles rendering of:
    - Service provider bindings
    - Configuration file content
    - Route definitions
    """

    def __init__(self):
        """Initialize the template engine."""
        self.templates_dir = Path(__file__).parent / "templates"

    def generate_service_provider(
        self,
        architecture: ProjectArchitecture,
        adapter_name: str,
        adapter_class: str,
        interface_class: str,
        namespace: str,
        conventions: Optional[CodeConventions] = None,
    ) -> str:
        """Generate service provider registration code.
        
        Args:
            architecture: Project architecture
            adapter_name: Name of the adapter (e.g., "DHL")
            adapter_class: Full class name of adapter
            interface_class: Interface to bind to
            namespace: Namespace of the adapter
            conventions: Code conventions to apply
            
        Returns:
            Generated service provider registration code
        """
        if not architecture.framework:
            return ""
        
        if architecture.framework == FrameworkType.LARAVEL:
            return self._generate_laravel_provider(
                adapter_name, adapter_class, interface_class, namespace
            )
        
        return ""

    def generate_config_file(
        self,
        architecture: ProjectArchitecture,
        service_name: str,
        adapters: list[str],
    ) -> str:
        """Generate configuration file content.
        
        Args:
            architecture: Project architecture
            service_name: Name of the service (e.g., "courier")
            adapters: List of adapter configurations
            
        Returns:
            Generated configuration file content
        """
        if not architecture.framework:
            return ""
        
        if architecture.framework == FrameworkType.LARAVEL:
            return self._generate_laravel_config(service_name, adapters)
        
        return ""

    def generate_routes(
        self,
        architecture: ProjectArchitecture,
        controller_class: str,
        methods: list[Dict[str, str]],
    ) -> str:
        """Generate route definitions.
        
        Args:
            architecture: Project architecture
            controller_class: Full controller class name
            methods: List of method definitions
            
        Returns:
            Generated route code
        """
        if not architecture.framework:
            return ""
        
        if architecture.framework == FrameworkType.LARAVEL:
            return self._generate_laravel_routes(controller_class, methods)
        
        return ""

    def _generate_laravel_provider(
        self,
        adapter_name: str,
        adapter_class: str,
        interface_class: str,
        namespace: str,
    ) -> str:
        """Generate Laravel service provider registration.
        
        Args:
            adapter_name: Name of the adapter
            adapter_class: Full adapter class name
            interface_class: Interface class name
            namespace: Adapter namespace
            
        Returns:
            Laravel service provider registration code
        """
        return f"""        // Register {adapter_name} adapter
        $this->app->bind('{interface_class}', {adapter_class}::class);"""

    def _generate_laravel_config(
        self,
        service_name: str,
        adapters: list[str],
    ) -> str:
        """Generate Laravel configuration array.
        
        Args:
            service_name: Service name (e.g., "courier")
            adapters: List of available adapters
            
        Returns:
            Laravel config PHP code
        """
        adapters_str = ",\n        ".join(f"'{adapter}'" for adapter in adapters)
        return f"""<?php

return [
    'default' => env('{service_name.upper()}_DRIVER', '{adapters[0].lower() if adapters else "default"}'),
    
    'drivers' => [
        {adapters_str},
    ],
];
"""

    def _generate_laravel_routes(
        self,
        controller_class: str,
        methods: list[Dict[str, str]],
    ) -> str:
        """Generate Laravel route definitions.
        
        Args:
            controller_class: Full controller class name
            methods: List of method definitions
            
        Returns:
            Laravel route code
        """
        routes = []
        for method in methods:
            http_method = method.get("method", "get").lower()
            route_path = method.get("path", "/")
            controller_method = method.get("action", "index")
            routes.append(
                f"Route::{http_method}('{route_path}', [{controller_class}::class, '{controller_method}']);"
            )
        
        return "\n        ".join(routes)
