"""
ProcessOS Agent Factory Module

Dynamic agent creation based on task requirements and capabilities.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .types import Agent, AgentCapability

if TYPE_CHECKING:
    from .registry import AgentRegistry


# Capability inference from step types
STEP_TYPE_CAPABILITIES = {
    "discovery": ["project_analysis", "file_scanning", "pattern_detection"],
    "intent_analysis": ["nlp", "intent_parsing", "request_classification"],
    "requirements_gather": ["requirement_inference", "material_detection"],
    "material_collection": ["api_parsing", "documentation_processing", "schema_extraction"],
    "schema_mapping": ["mapping", "field_matching", "type_inference"],
    "user_confirmation": ["interaction", "user_prompt"],
    "code_generation": ["code_generation", "templating", "file_creation"],
    "code_review": ["code_review", "diff_analysis"],
    "code_application": ["file_writing", "patchset_application"],
}

# Agent templates for common scenarios
AGENT_TEMPLATES = {
    "mapper": {
        "name": "Schema Mapper Agent",
        "capabilities": ["mapping", "field_matching", "type_inference"],
        "system_prompt": "You are a schema mapping agent. Your task is to map external API schemas to local models.",
        "input_contract": {"external_schema": "dict", "local_models": "list"},
        "output_contract": {"mappings": "list", "confidence_scores": "dict"},
    },
    "codegen": {
        "name": "Code Generator Agent",
        "capabilities": ["code_generation", "templating", "convention_adherence"],
        "system_prompt": "You are a code generation agent. Generate code following project conventions.",
        "input_contract": {"mapping": "dict", "conventions": "dict"},
        "output_contract": {"files": "list", "diff": "str"},
    },
    "analyzer": {
        "name": "Project Analyzer Agent",
        "capabilities": ["project_analysis", "pattern_detection", "convention_inference"],
        "system_prompt": "You are a project analyzer. Discover project structure and conventions.",
        "input_contract": {"project_root": "str"},
        "output_contract": {"models": "list", "routes": "list", "conventions": "dict"},
    },
    "collector": {
        "name": "Material Collector Agent",
        "capabilities": ["api_parsing", "documentation_processing", "schema_extraction"],
        "system_prompt": "You are a material collector. Gather API documentation and credentials.",
        "input_contract": {"source_url": "str", "source_type": "str"},
        "output_contract": {"api_docs": "dict", "endpoints": "list"},
    },
}


class AgentFactory:
    """
    Factory for creating dynamic agents.

    Features:
    - Create agents from capability requirements
    - Infer capabilities from step types
    - Use templates for common agent types
    - Find matching existing agents
    """

    def __init__(
        self,
        registry: Optional["AgentRegistry"] = None,
    ):
        """
        Initialize the factory.

        Args:
            registry: Optional registry for finding existing agents
        """
        self.registry = registry
        self._created_agents: Dict[str, Agent] = {}

    def create_agent(
        self,
        capabilities: List[str],
        name: Optional[str] = None,
        input_contract: Optional[Dict[str, Any]] = None,
        output_contract: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        context_requirements: Optional[List[str]] = None,
    ) -> Agent:
        """
        Create a new agent with specified capabilities.

        Args:
            capabilities: List of capability names
            name: Optional agent name
            input_contract: Optional input schema
            output_contract: Optional output schema
            system_prompt: Optional system prompt
            context_requirements: Optional context requirements

        Returns:
            New Agent instance
        """
        agent_id = str(uuid.uuid4())[:8]

        # Build capability objects
        capability_objs = [
            AgentCapability(
                name=cap,
                description=f"Capability: {cap}",
                semantic_tags=self._get_capability_tags(cap),
            )
            for cap in capabilities
        ]

        # Generate default name if not provided
        if not name:
            primary_cap = capabilities[0] if capabilities else "general"
            name = f"{primary_cap.replace('_', ' ').title()} Agent"

        agent = Agent(
            id=agent_id,
            name=name,
            capabilities=capability_objs,
            input_contract=input_contract or {},
            output_contract=output_contract or {},
            system_prompt=system_prompt or "",
            context_requirements=context_requirements or [],
        )

        self._created_agents[agent_id] = agent
        return agent

    def create_from_template(
        self,
        template_name: str,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """
        Create an agent from a predefined template.

        Args:
            template_name: Name of template to use
            customizations: Optional customizations to apply

        Returns:
            New Agent instance

        Raises:
            ValueError: If template not found
        """
        template = AGENT_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        # Apply customizations
        if customizations:
            template = {**template, **customizations}

        return self.create_agent(
            capabilities=template.get("capabilities", []),
            name=template.get("name"),
            input_contract=template.get("input_contract"),
            output_contract=template.get("output_contract"),
            system_prompt=template.get("system_prompt"),
            context_requirements=template.get("context_requirements"),
        )

    def infer_capabilities(
        self,
        step_type: str,
    ) -> List[str]:
        """
        Infer capabilities needed for a step type.

        Args:
            step_type: Type of playbook step

        Returns:
            List of capability names
        """
        # Normalize step type
        step_type_lower = step_type.lower().replace("-", "_")

        # Look up in mapping
        capabilities = STEP_TYPE_CAPABILITIES.get(step_type_lower, [])

        if not capabilities:
            # Generate generic capability based on step type
            capabilities = [step_type_lower]

        return capabilities

    def find_matching_agent(
        self,
        required_capabilities: List[str],
    ) -> Optional[str]:
        """
        Find an existing agent that matches required capabilities.

        Args:
            required_capabilities: Capabilities the agent must have

        Returns:
            Agent ID if found, None otherwise
        """
        if not self.registry:
            return None

        # Check registry for matching agents
        all_agents = self.registry.load_all()

        best_match = None
        best_score = 0

        for agent_id, agent_data in all_agents.items():
            agent_caps = set(agent_data.get("capabilities", []))
            required_set = set(required_capabilities)

            # Calculate match score
            matched = agent_caps & required_set
            if len(matched) == len(required_set):
                # All required capabilities present
                score = len(matched)
                if score > best_score:
                    best_score = score
                    best_match = agent_id

        return best_match

    def get_or_create_agent(
        self,
        capabilities: List[str],
        name: Optional[str] = None,
    ) -> Agent:
        """
        Get an existing agent or create a new one.

        Args:
            capabilities: Required capabilities
            name: Optional agent name for new agent

        Returns:
            Agent instance
        """
        # Try to find existing
        existing_id = self.find_matching_agent(capabilities)
        if existing_id:
            # Load from registry and convert to Agent
            agent_data = self.registry.load(existing_id)
            return Agent.from_dict({
                "id": existing_id,
                "name": agent_data.get("name", "Unknown"),
                "capabilities": [
                    {"name": c, "description": f"Capability: {c}", "semantic_tags": []}
                    for c in agent_data.get("capabilities", [])
                ],
                "input_contract": agent_data.get("input_contract", {}),
                "output_contract": agent_data.get("output_contract", {}),
                "system_prompt": agent_data.get("system_prompt", ""),
                "context_requirements": agent_data.get("context_requirements", []),
            })

        # Create new
        return self.create_agent(capabilities=capabilities, name=name)

    def _get_capability_tags(self, capability: str) -> List[str]:
        """Get semantic tags for a capability."""
        # Generate tags from capability name
        parts = capability.lower().replace("-", "_").split("_")
        tags = parts + [capability]

        # Add related tags
        tag_relations = {
            "mapping": ["schema", "field", "transform"],
            "generation": ["code", "template", "create"],
            "parsing": ["extract", "analyze", "read"],
            "validation": ["check", "verify", "test"],
        }

        for key, related in tag_relations.items():
            if key in tags:
                tags.extend(related)

        return list(set(tags))

    def list_templates(self) -> List[str]:
        """List available agent templates."""
        return list(AGENT_TEMPLATES.keys())

    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a template."""
        return AGENT_TEMPLATES.get(template_name)
