"""
ProcessOS Squad Generator

Generates deterministic squad bundles from SquadRequest objects.
Same input = byte-identical output.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml

from .command_parser import SquadRequest


@dataclass
class AgentCard:
    """Agent role card."""
    agent_id: str
    name: str
    role: str
    capabilities: List[str]
    constraints: List[str]
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    prompt_template: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
        return {
            "agent_id": self.agent_id,
            "capabilities": sorted(self.capabilities),
            "constraints": sorted(self.constraints),
            "inputs": dict(sorted(self.inputs.items())),
            "name": self.name,
            "outputs": dict(sorted(self.outputs.items())),
            "prompt_template": self.prompt_template,
            "role": self.role,
        }

    def to_yaml(self) -> str:
        """Serialize to deterministic YAML."""
        return yaml.dump(self.to_dict(), sort_keys=True, default_flow_style=False)


@dataclass
class Gate:
    """Gate definition."""
    gate_id: str
    gate_type: str
    description: str
    parameters: Dict[str, Any]
    on_failure: str = "halt_with_reason"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "gate_id": self.gate_id,
            "gate_type": self.gate_type,
            "on_failure": self.on_failure,
            "parameters": dict(sorted(self.parameters.items())),
        }


@dataclass
class PlaybookStep:
    """Playbook step definition."""
    step_id: str
    description: str
    agent_id: str
    sequence: int
    inputs_spec: Dict[str, Any]
    outputs_spec: Dict[str, Any]
    gates: List[Gate] = field(default_factory=list)
    prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "agent_id": self.agent_id,
            "description": self.description,
            "inputs_spec": dict(sorted(self.inputs_spec.items())) if self.inputs_spec else {},
            "outputs_spec": dict(sorted(self.outputs_spec.items())) if self.outputs_spec else {},
            "sequence": self.sequence,
            "step_id": self.step_id,
        }
        if self.gates:
            result["gates"] = [g.to_dict() for g in self.gates]
        if self.prompt:
            result["prompt"] = self.prompt
        return result


@dataclass
class Playbook:
    """Generated playbook."""
    playbook_id: str
    playbook_version: str
    description: str
    steps: List[PlaybookStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "playbook_id": self.playbook_id,
            "playbook_version": self.playbook_version,
            "steps": [s.to_dict() for s in sorted(self.steps, key=lambda s: s.sequence)],
        }

    def to_yaml(self) -> str:
        """Serialize to deterministic YAML."""
        return yaml.dump(self.to_dict(), sort_keys=False, default_flow_style=False, allow_unicode=True)


@dataclass
class SquadBundle:
    """Complete squad bundle output."""
    request_id: str
    playbook: Playbook
    agents: List[AgentCard]
    templates: Dict[str, str]  # template_name -> content
    gates: List[Gate]

    def get_manifest(self) -> Dict[str, Any]:
        """Get bundle manifest with SHA256 hashes."""
        return {
            "request_id": self.request_id,
            "playbook_id": self.playbook.playbook_id,
            "playbook_sha256": hashlib.sha256(self.playbook.to_yaml().encode()).hexdigest(),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "sha256": hashlib.sha256(a.to_yaml().encode()).hexdigest(),
                }
                for a in sorted(self.agents, key=lambda a: a.agent_id)
            ],
            "templates": [
                {
                    "name": name,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
                for name, content in sorted(self.templates.items())
            ],
            "gates_count": len(self.gates),
        }


class SquadGenerator:
    """
    Generates deterministic squad bundles from SquadRequest.

    Determinism guarantees:
    - Sorted keys in all outputs
    - Stable ID generation from inputs
    - No timestamps in generated content
    - Reproducible template rendering
    """

    # Agent templates for different command types
    # NOTE: These are now GENERIC templates. Specific agent configurations
    # are created dynamically by the agents/ module based on integration requirements.
    # See: process_os/agents/factory.py for dynamic agent creation
    AGENT_TEMPLATES = {
        "integration": [
            {
                "suffix": "discovery-agent",
                "name": "Discovery Agent",
                "role": "Analyzes project structure and discovers patterns",
                "capabilities": ["project_analysis", "pattern_detection", "convention_inference"],
                "constraints": ["read_only_access", "no_code_execution"],
            },
            {
                "suffix": "intent-agent",
                "name": "Intent Agent",
                "role": "Analyzes user intent and classifies integration type",
                "capabilities": ["intent_analysis", "classification", "clarification"],
                "constraints": ["deterministic_output"],
            },
            {
                "suffix": "mapping-agent",
                "name": "Mapping Agent",
                "role": "Maps external schemas to local models",
                "capabilities": ["schema_analysis", "field_mapping", "transformation_rules"],
                "constraints": ["no_external_calls", "deterministic_output"],
            },
            {
                "suffix": "codegen-agent",
                "name": "Code Generation Agent",
                "role": "Generates code following project conventions",
                "capabilities": ["code_generation", "convention_adherence", "test_generation"],
                "constraints": ["follow_conventions", "user_review_required"],
            },
        ],
        "custom": [
            {
                "suffix": "analyst",
                "name": "Analyst",
                "role": "Analyzes requirements and produces structured output",
                "capabilities": ["analysis", "structured_output"],
                "constraints": ["deterministic_output"],
            },
        ],
    }

    # Template content for different artifact types
    TEMPLATE_CONTENT = {
        "intake-summary": """# Intake Summary: {{ target_name }}

## Overview
{{ summary }}

## Capabilities Identified
{% for cap in capabilities %}
- {{ cap }}
{% endfor %}

## Constraints
{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}

## Next Steps
{{ next_steps }}

---
*Generated by ProcessOS Squad Factory*
""",
        "api-mapping": """# API Mapping: {{ target_name }}

## Source API
{{ source_description }}

## Target Contract
{{ target_description }}

## Field Mappings
| Source Field | Target Field | Transform |
|--------------|--------------|-----------|
{% for mapping in mappings %}
| {{ mapping.source }} | {{ mapping.target }} | {{ mapping.transform }} |
{% endfor %}

## Validation Rules
{% for rule in validation_rules %}
- {{ rule }}
{% endfor %}

---
*Generated by ProcessOS Squad Factory*
""",
        "detection-report": """# Detection Report: {{ target_name }}

## Detection Rules
{% for rule in rules %}
### {{ rule.name }}
- Pattern: `{{ rule.pattern }}`
- Priority: {{ rule.priority }}
- Action: {{ rule.action }}

{% endfor %}

## Summary
- Total Rules: {{ rules | length }}
- Coverage: {{ coverage }}

---
*Generated by ProcessOS Squad Factory*
""",
    }

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize generator.

        Args:
            templates_dir: Optional custom templates directory
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir

    def _generate_id(self, prefix: str, data: Dict[str, Any]) -> str:
        """Generate deterministic ID from data."""
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        hash_hex = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        return f"{prefix}-{hash_hex}"

    def _create_agents(self, request: SquadRequest) -> List[AgentCard]:
        """Create agent cards for the request."""
        agents = []
        templates = self.AGENT_TEMPLATES.get(request.command_type, self.AGENT_TEMPLATES["custom"])

        for idx, template in enumerate(templates):
            agent_id = f"{request.target['identifier']}-{template['suffix']}"

            # Build inputs based on sequence
            inputs = {}
            if idx == 0:
                inputs["raw_input"] = {
                    "type": "string",
                    "required": True,
                    "description": "Initial input data",
                }
            else:
                prev_agent = templates[idx - 1]["suffix"]
                inputs["previous_output"] = {
                    "type": "artifact",
                    "required": True,
                    "description": f"Output from {prev_agent}",
                }

            # Build outputs
            outputs = {
                "result": {
                    "type": "artifact",
                    "artifact_kind": f"{template['suffix']}-output",
                    "description": f"Output from {template['name']}",
                }
            }

            # Build prompt template
            prompt_template = f"""You are {template['name']}.

Your role: {template['role']}

CAPABILITIES:
{chr(10).join(f'- {cap}' for cap in template['capabilities'])}

CONSTRAINTS:
{chr(10).join(f'- {con}' for con in template['constraints'])}

TASK:
Analyze the input and produce a structured JSON response.

INPUT:
{{{{ input_data }}}}

CRITICAL: Respond with ONLY valid JSON matching the output schema.
"""

            agent = AgentCard(
                agent_id=agent_id,
                name=template["name"],
                role=template["role"],
                capabilities=template["capabilities"],
                constraints=template["constraints"],
                inputs=inputs,
                outputs=outputs,
                prompt_template=prompt_template,
            )
            agents.append(agent)

        return agents

    def _create_gates(self, request: SquadRequest, agents: List[AgentCard]) -> List[Gate]:
        """Create gates for the playbook."""
        gates = []

        for idx, agent in enumerate(agents):
            if idx > 0:
                # Gate requiring previous step's artifact
                prev_agent = agents[idx - 1]
                gate = Gate(
                    gate_id=f"gate-{agent.agent_id}-requires-{prev_agent.agent_id}",
                    gate_type="artifact_exists",
                    description=f"Requires output from {prev_agent.name}",
                    parameters={
                        "artifact_kind": f"{prev_agent.agent_id.split('-')[-1]}-output",
                    },
                    on_failure="halt_with_reason",
                )
                gates.append(gate)

        # Final validation gate
        if agents:
            final_gate = Gate(
                gate_id=f"gate-{request.target['identifier']}-complete",
                gate_type="all_artifacts_present",
                description="All required artifacts must be present",
                parameters={
                    "required_artifacts": [f"{a.agent_id.split('-')[-1]}-output" for a in agents],
                },
                on_failure="halt_with_reason",
            )
            gates.append(final_gate)

        return gates

    def _create_steps(self, request: SquadRequest, agents: List[AgentCard], gates: List[Gate]) -> List[PlaybookStep]:
        """Create playbook steps from agents."""
        steps = []

        # Build gate lookup by agent
        gate_lookup: Dict[str, List[Gate]] = {}
        for gate in gates:
            if gate.gate_type == "artifact_exists":
                # Find which agent this gate is for
                for agent in agents:
                    if agent.agent_id in gate.gate_id:
                        if agent.agent_id not in gate_lookup:
                            gate_lookup[agent.agent_id] = []
                        gate_lookup[agent.agent_id].append(gate)
                        break

        for idx, agent in enumerate(agents):
            step_gates = gate_lookup.get(agent.agent_id, [])

            step = PlaybookStep(
                step_id=f"step-{idx + 1}-{agent.agent_id}",
                description=f"Execute {agent.name}",
                agent_id=agent.agent_id,
                sequence=idx + 1,
                inputs_spec=agent.inputs,
                outputs_spec=agent.outputs,
                gates=step_gates,
                prompt=agent.prompt_template,
            )
            steps.append(step)

        return steps

    def _create_playbook(self, request: SquadRequest, steps: List[PlaybookStep]) -> Playbook:
        """Create playbook from steps."""
        playbook_id = f"playbook-{request.target['identifier']}"

        return Playbook(
            playbook_id=playbook_id,
            playbook_version="1.0.0",
            description=f"Generated playbook for {request.target['name']} ({request.command_type})",
            steps=steps,
        )

    def _create_templates(self, request: SquadRequest) -> Dict[str, str]:
        """Create artifact templates for the request.

        NOTE: Templates are now generic. Specific templates are generated
        dynamically by the playbook/ module based on integration requirements.
        """
        templates = {}

        # All integrations use the generic templates
        # Specific artifact templates are generated dynamically
        templates["intake-summary.md.j2"] = self.TEMPLATE_CONTENT["intake-summary"]
        templates["api-mapping.md.j2"] = self.TEMPLATE_CONTENT["api-mapping"]

        return templates

    def generate(self, request: SquadRequest) -> SquadBundle:
        """
        Generate squad bundle from request.

        Args:
            request: Validated SquadRequest

        Returns:
            SquadBundle with all generated artifacts
        """
        # Create components in dependency order
        agents = self._create_agents(request)
        gates = self._create_gates(request, agents)
        steps = self._create_steps(request, agents, gates)
        playbook = self._create_playbook(request, steps)
        templates = self._create_templates(request)

        return SquadBundle(
            request_id=request.request_id,
            playbook=playbook,
            agents=agents,
            templates=templates,
            gates=gates,
        )

    def write_bundle(self, bundle: SquadBundle, output_dir: Path) -> Dict[str, Path]:
        """
        Write bundle to disk.

        Args:
            bundle: Generated SquadBundle
            output_dir: Target directory

        Returns:
            Dict mapping artifact type to written file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        written_files: Dict[str, Path] = {}

        # Write playbook
        playbook_path = output_dir / "playbook.yaml"
        playbook_path.write_text(bundle.playbook.to_yaml())
        written_files["playbook"] = playbook_path

        # Write agents
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        for agent in bundle.agents:
            agent_path = agents_dir / f"{agent.agent_id}.yaml"
            agent_path.write_text(agent.to_yaml())
            written_files[f"agent:{agent.agent_id}"] = agent_path

        # Write templates
        templates_dir = output_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        for name, content in bundle.templates.items():
            template_path = templates_dir / name
            template_path.write_text(content)
            written_files[f"template:{name}"] = template_path

        # Write manifest
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(bundle.get_manifest(), sort_keys=True, indent=2))
        written_files["manifest"] = manifest_path

        return written_files
