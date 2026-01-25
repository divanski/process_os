"""
ProcessOS Workspace Generator

Generates complete workspaces from TaskRequests.
Each workspace is an isolated environment containing playbook, agents, templates, and gates.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..commands.task_request import TaskRequest


@dataclass
class WorkspaceManifest:
    """Manifest for a generated workspace."""

    workspace_id: str
    command_id: str
    created_at: str
    intent: str
    target: Dict[str, str]
    contents: Dict[str, Any]
    hashes: Dict[str, str] = field(default_factory=dict)
    runs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
        return {
            "command_id": self.command_id,
            "contents": {
                "agents": sorted(self.contents.get("agents", []), key=lambda x: x["agent_id"]),
                "gates": sorted(self.contents.get("gates", []), key=lambda x: x["gate_id"]),
                "playbook": self.contents.get("playbook", ""),
                "templates": sorted(self.contents.get("templates", []), key=lambda x: x["template_id"]),
            },
            "created_at": self.created_at,
            "hashes": dict(sorted(self.hashes.items())),
            "intent": self.intent,
            "runs": self.runs,
            "target": dict(sorted(self.target.items())),
            "workspace_id": self.workspace_id,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to deterministic JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), sort_keys=True, default_flow_style=False)


@dataclass
class AgentCard:
    """Agent role card for workspace."""

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
    """Gate definition for workspace."""

    gate_id: str
    gate_type: str
    description: str
    parameters: Dict[str, Any]
    on_failure: str = "halt"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
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
        return result


@dataclass
class InboxGateConfig:
    """Inbox gate configuration for playbook."""

    gate_id: str
    integration_id: str
    required_one_of: List[str]
    require_secrets_file: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
        return {
            "gate_id": self.gate_id,
            "integration_id": self.integration_id,
            "require_secrets_file": self.require_secrets_file,
            "required_one_of": sorted(self.required_one_of),
        }


@dataclass
class Playbook:
    """Generated playbook for workspace."""

    playbook_id: str
    playbook_version: str
    description: str
    command_id: str
    workspace_id: str
    steps: List[PlaybookStep]
    inbox_gates: List[InboxGateConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sorted dictionary."""
        result = {
            "command_id": self.command_id,
            "description": self.description,
            "playbook_id": self.playbook_id,
            "playbook_version": self.playbook_version,
            "steps": [s.to_dict() for s in sorted(self.steps, key=lambda s: s.sequence)],
            "workspace_id": self.workspace_id,
        }
        if self.inbox_gates:
            result["inbox_gates"] = [g.to_dict() for g in self.inbox_gates]
        return result

    def to_yaml(self) -> str:
        """Serialize to deterministic YAML."""
        return yaml.dump(self.to_dict(), sort_keys=False, default_flow_style=False)


@dataclass
class Workspace:
    """Complete workspace with all generated artifacts."""

    workspace_id: str
    command_id: str
    manifest: WorkspaceManifest
    playbook: Playbook
    agents: List[AgentCard]
    templates: Dict[str, str]
    gates: List[Gate]

    def get_file_hashes(self) -> Dict[str, str]:
        """Calculate SHA256 hashes for all generated content."""
        hashes = {}

        # Playbook hash
        hashes["playbook.yaml"] = hashlib.sha256(
            self.playbook.to_yaml().encode()
        ).hexdigest()

        # Agent hashes
        for agent in self.agents:
            filename = f"agents/{agent.agent_id}.yaml"
            hashes[filename] = hashlib.sha256(agent.to_yaml().encode()).hexdigest()

        # Template hashes
        for name, content in self.templates.items():
            filename = f"templates/{name}"
            hashes[filename] = hashlib.sha256(content.encode()).hexdigest()

        return hashes


class WorkspaceGenerator:
    """
    Generates complete workspaces from TaskRequests.

    Determinism guarantees:
    - Same TaskRequest = same workspace_id
    - Same TaskRequest = byte-identical generated files
    - Sorted keys in all outputs
    - No timestamps in generated content (only in manifest)
    """

    # Agent templates by intent
    AGENT_BLUEPRINTS = {
        "integrate": [
            {
                "suffix": "intake-analyst",
                "name": "Intake Analyst",
                "role": "Analyzes documentation and extracts capabilities",
                "capabilities": ["document_analysis", "capability_extraction"],
                "constraints": ["read_only", "no_code_execution"],
            },
            {
                "suffix": "mapper",
                "name": "Integration Mapper",
                "role": "Maps source to target contracts",
                "capabilities": ["contract_mapping", "field_mapping"],
                "constraints": ["deterministic_output", "explicit_mappings"],
            },
            {
                "suffix": "validator",
                "name": "Integration Validator",
                "role": "Validates integration completeness",
                "capabilities": ["validation", "completeness_check"],
                "constraints": ["halt_on_failure"],
            },
        ],
        "map_api": [
            {
                "suffix": "schema-analyst",
                "name": "Schema Analyst",
                "role": "Analyzes API schemas and structures",
                "capabilities": ["schema_analysis", "type_inference"],
                "constraints": ["read_only"],
            },
            {
                "suffix": "field-mapper",
                "name": "Field Mapper",
                "role": "Maps fields between schemas",
                "capabilities": ["field_mapping", "transformation_rules"],
                "constraints": ["explicit_mappings_only"],
            },
        ],
        "detect": [
            {
                "suffix": "pattern-analyst",
                "name": "Pattern Analyst",
                "role": "Identifies detection patterns",
                "capabilities": ["pattern_detection", "rule_extraction"],
                "constraints": ["no_false_positives"],
            },
            {
                "suffix": "rule-generator",
                "name": "Rule Generator",
                "role": "Generates detection rules",
                "capabilities": ["rule_generation", "priority_assignment"],
                "constraints": ["explicit_rules_only"],
            },
        ],
        "analyze": [
            {
                "suffix": "analyst",
                "name": "Analyst",
                "role": "Performs analysis and produces insights",
                "capabilities": ["analysis", "insight_generation"],
                "constraints": ["structured_output"],
            },
        ],
        "generate": [
            {
                "suffix": "generator",
                "name": "Generator",
                "role": "Generates requested artifacts",
                "capabilities": ["code_generation", "artifact_generation"],
                "constraints": ["schema_compliant"],
            },
        ],
        "validate": [
            {
                "suffix": "validator",
                "name": "Validator",
                "role": "Validates inputs against rules",
                "capabilities": ["validation", "rule_checking"],
                "constraints": ["halt_on_failure"],
            },
        ],
        "custom": [
            {
                "suffix": "agent",
                "name": "Task Agent",
                "role": "Executes custom task",
                "capabilities": ["task_execution"],
                "constraints": ["structured_output"],
            },
        ],
    }

    # Template content by artifact type
    TEMPLATE_CONTENT = {
        "intake-summary.md.j2": """# Intake Summary: {{ target_name }}

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
*Generated by ProcessOS*
""",
        "api-mapping.md.j2": """# API Mapping: {{ target_name }}

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
*Generated by ProcessOS*
""",
        "detection-report.md.j2": """# Detection Report: {{ target_name }}

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
*Generated by ProcessOS*
""",
        "validation-report.md.j2": """# Validation Report: {{ target_name }}

## Validation Results
{% for result in results %}
### {{ result.check }}
- Status: {{ result.status }}
- Details: {{ result.details }}

{% endfor %}

## Summary
- Passed: {{ passed_count }}
- Failed: {{ failed_count }}
- Total: {{ total_count }}

---
*Generated by ProcessOS*
""",
    }

    def __init__(self, workspaces_root: Optional[Path] = None):
        """
        Initialize generator.

        Args:
            workspaces_root: Root directory for workspaces
        """
        if workspaces_root is None:
            workspaces_root = Path(__file__).parent.parent / "workspaces"
        self.workspaces_root = Path(workspaces_root)

    def _create_agents(self, request: TaskRequest) -> List[AgentCard]:
        """Create agent cards based on request intent."""
        blueprints = self.AGENT_BLUEPRINTS.get(
            request.intent, self.AGENT_BLUEPRINTS["custom"]
        )
        agents = []

        for idx, bp in enumerate(blueprints):
            agent_id = f"{request.target.identifier}-{bp['suffix']}"

            # Build inputs based on sequence
            inputs: Dict[str, Any] = {}
            if idx == 0:
                inputs["raw_input"] = {
                    "description": "Initial input data",
                    "required": True,
                    "type": "string",
                }
            else:
                prev_bp = blueprints[idx - 1]
                inputs["previous_output"] = {
                    "description": f"Output from {prev_bp['name']}",
                    "required": True,
                    "type": "artifact",
                }

            # Build outputs
            outputs = {
                "result": {
                    "artifact_kind": f"{bp['suffix']}-output",
                    "description": f"Output from {bp['name']}",
                    "type": "artifact",
                }
            }

            # Build prompt template
            prompt_template = f"""You are {bp['name']}.

Your role: {bp['role']}

CAPABILITIES:
{chr(10).join(f'- {cap}' for cap in bp['capabilities'])}

CONSTRAINTS:
{chr(10).join(f'- {con}' for con in bp['constraints'])}

TASK:
Process the input and produce a structured JSON response.

INPUT:
{{{{ input_data }}}}

Respond with valid JSON only.
"""

            agent = AgentCard(
                agent_id=agent_id,
                name=bp["name"],
                role=bp["role"],
                capabilities=bp["capabilities"],
                constraints=bp["constraints"],
                inputs=inputs,
                outputs=outputs,
                prompt_template=prompt_template,
            )
            agents.append(agent)

        return agents

    def _create_gates(self, request: TaskRequest, agents: List[AgentCard]) -> List[Gate]:
        """Create gates for workflow control."""
        gates = []

        for idx, agent in enumerate(agents):
            if idx > 0:
                # Gate requiring previous agent's output
                prev_agent = agents[idx - 1]
                artifact_kind = f"{prev_agent.agent_id.split('-')[-1]}-output"

                gate = Gate(
                    gate_id=f"gate-requires-{prev_agent.agent_id}",
                    gate_type="artifact_exists",
                    description=f"Requires output from {prev_agent.name}",
                    parameters={"artifact_kind": artifact_kind},
                    on_failure="halt",
                )
                gates.append(gate)

        # Final completion gate
        if agents:
            required = [f"{a.agent_id.split('-')[-1]}-output" for a in agents]
            final_gate = Gate(
                gate_id=f"gate-{request.target.identifier}-complete",
                gate_type="all_artifacts_present",
                description="All required artifacts must be present",
                parameters={"required_artifacts": sorted(required)},
                on_failure="halt",
            )
            gates.append(final_gate)

        return gates

    def _create_steps(
        self, request: TaskRequest, agents: List[AgentCard], gates: List[Gate]
    ) -> List[PlaybookStep]:
        """Create playbook steps from agents."""
        steps = []

        # Build gate lookup
        gate_by_agent: Dict[str, List[Gate]] = {}
        for gate in gates:
            if gate.gate_type == "artifact_exists":
                # This gate is for the NEXT agent after the one it requires
                required_kind = gate.parameters.get("artifact_kind", "")
                for i, agent in enumerate(agents):
                    if i > 0:
                        prev_agent = agents[i - 1]
                        if required_kind == f"{prev_agent.agent_id.split('-')[-1]}-output":
                            if agent.agent_id not in gate_by_agent:
                                gate_by_agent[agent.agent_id] = []
                            gate_by_agent[agent.agent_id].append(gate)

        for idx, agent in enumerate(agents):
            step_gates = gate_by_agent.get(agent.agent_id, [])

            step = PlaybookStep(
                step_id=f"step-{idx + 1}-{agent.agent_id}",
                description=f"Execute {agent.name}",
                agent_id=agent.agent_id,
                sequence=idx + 1,
                inputs_spec=agent.inputs,
                outputs_spec=agent.outputs,
                gates=step_gates,
            )
            steps.append(step)

        return steps

    def _create_playbook(
        self,
        request: TaskRequest,
        workspace_id: str,
        steps: List[PlaybookStep],
    ) -> Playbook:
        """Create playbook for workspace."""
        playbook_id = f"playbook-{request.target.identifier}"

        # Create inbox gates for courier integrations
        inbox_gates: List[InboxGateConfig] = []
        if request.intent == "integrate" and request.target.type == "courier":
            integration_id = request.target.identifier.lower()
            inbox_gates.append(
                InboxGateConfig(
                    gate_id=f"inbox_materials_check_{integration_id}",
                    integration_id=integration_id,
                    required_one_of=[
                        "*.postman_collection.json",
                        "openapi.yaml",
                        "openapi.json",
                        "swagger.yaml",
                        "swagger.json",
                        "curl_examples.md",
                        "api_docs.md",
                    ],
                    require_secrets_file=True,
                )
            )

        return Playbook(
            playbook_id=playbook_id,
            playbook_version="1.0.0",
            description=f"Playbook for {request.target.name} ({request.intent})",
            command_id=request.command_id,
            workspace_id=workspace_id,
            steps=steps,
            inbox_gates=inbox_gates,
        )

    def _select_templates(self, request: TaskRequest) -> Dict[str, str]:
        """Select templates based on intent."""
        templates = {}

        # Map intents to templates
        intent_templates = {
            "integrate": ["intake-summary.md.j2", "api-mapping.md.j2"],
            "map_api": ["api-mapping.md.j2"],
            "detect": ["detection-report.md.j2"],
            "analyze": ["intake-summary.md.j2"],
            "generate": ["intake-summary.md.j2"],
            "validate": ["validation-report.md.j2"],
            "custom": ["intake-summary.md.j2"],
        }

        template_names = intent_templates.get(
            request.intent, intent_templates["custom"]
        )

        for name in template_names:
            if name in self.TEMPLATE_CONTENT:
                templates[name] = self.TEMPLATE_CONTENT[name]

        return templates

    def generate(self, request: TaskRequest) -> Workspace:
        """
        Generate workspace from TaskRequest.

        Args:
            request: Validated TaskRequest

        Returns:
            Workspace with all generated artifacts
        """
        # Generate workspace ID from command ID
        workspace_id = request.get_workspace_id()

        # Create components
        agents = self._create_agents(request)
        gates = self._create_gates(request, agents)
        steps = self._create_steps(request, agents, gates)
        playbook = self._create_playbook(request, workspace_id, steps)
        templates = self._select_templates(request)

        # Build manifest contents
        contents = {
            "playbook": "playbook.yaml",
            "agents": [
                {"agent_id": a.agent_id, "path": f"agents/{a.agent_id}.yaml"}
                for a in sorted(agents, key=lambda a: a.agent_id)
            ],
            "templates": [
                {"template_id": name, "path": f"templates/{name}"}
                for name in sorted(templates.keys())
            ],
            "gates": [
                {"gate_id": g.gate_id, "type": g.gate_type}
                for g in sorted(gates, key=lambda g: g.gate_id)
            ],
        }

        # Create manifest (timestamp is in manifest, not in generated files)
        manifest = WorkspaceManifest(
            workspace_id=workspace_id,
            command_id=request.command_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            intent=request.intent,
            target={
                "identifier": request.target.identifier,
                "name": request.target.name,
                "type": request.target.type,
            },
            contents=contents,
            hashes={},
            runs=[],
        )

        # Create workspace
        workspace = Workspace(
            workspace_id=workspace_id,
            command_id=request.command_id,
            manifest=manifest,
            playbook=playbook,
            agents=agents,
            templates=templates,
            gates=gates,
        )

        # Calculate hashes and update manifest
        workspace.manifest.hashes = workspace.get_file_hashes()

        return workspace

    def write_workspace(self, workspace: Workspace) -> Path:
        """
        Write workspace to disk.

        Args:
            workspace: Generated Workspace

        Returns:
            Path to workspace directory
        """
        workspace_dir = self.workspaces_root / workspace.workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Write playbook
        playbook_path = workspace_dir / "playbook.yaml"
        playbook_path.write_text(workspace.playbook.to_yaml())

        # Write agents
        agents_dir = workspace_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        for agent in workspace.agents:
            agent_path = agents_dir / f"{agent.agent_id}.yaml"
            agent_path.write_text(agent.to_yaml())

        # Write templates
        templates_dir = workspace_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        for name, content in workspace.templates.items():
            template_path = templates_dir / name
            template_path.write_text(content)

        # Write gates as YAML
        gates_dir = workspace_dir / "gates"
        gates_dir.mkdir(exist_ok=True)
        gates_data = [g.to_dict() for g in sorted(workspace.gates, key=lambda g: g.gate_id)]
        gates_path = gates_dir / "gates.yaml"
        gates_path.write_text(yaml.dump(gates_data, sort_keys=True, default_flow_style=False))

        # Create runs directory
        runs_dir = workspace_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        (runs_dir / ".gitkeep").write_text("")

        # Write manifest last (after hashes are computed)
        manifest_path = workspace_dir / "manifest.yaml"
        manifest_path.write_text(workspace.manifest.to_yaml())

        return workspace_dir

    def load_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """
        Load existing workspace from disk.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Workspace if found, None otherwise
        """
        workspace_dir = self.workspaces_root / workspace_id
        if not workspace_dir.exists():
            return None

        manifest_path = workspace_dir / "manifest.yaml"
        if not manifest_path.exists():
            return None

        # Load manifest
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        # This is a simplified load - full implementation would reconstruct all objects
        # For now, return None to indicate workspace exists but full load not implemented
        return None

    def workspace_exists(self, workspace_id: str) -> bool:
        """Check if workspace exists."""
        workspace_dir = self.workspaces_root / workspace_id
        return (workspace_dir / "manifest.yaml").exists()
