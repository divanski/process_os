"""
ProcessOS Integration Runner

Orchestrates the full dynamic integration workflow:
Discovery → Intent → Requirements → Mapping → Codegen → Playbook
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..discovery import ProjectContext, discover_project
from ..intent import Intent, parse_intent
from ..requirements import Requirements, MaterialCollection, infer_requirements, MaterialCollector
from ..mapping import SchemaMapping, map_schemas, InteractiveMapper
from ..codegen import GeneratedCode, generate_integration_code, PatchsetManager
from ..playbook import DynamicPlaybook, build_playbook


class WorkflowState(Enum):
    """State of the integration workflow."""

    INITIALIZED = "initialized"
    DISCOVERING = "discovering"
    PARSING_INTENT = "parsing_intent"
    CLARIFYING = "clarifying"
    INFERRING_REQUIREMENTS = "inferring_requirements"
    COLLECTING_MATERIALS = "collecting_materials"
    MAPPING_SCHEMAS = "mapping_schemas"
    REVIEWING_MAPPING = "reviewing_mapping"
    BUILDING_PLAYBOOK = "building_playbook"
    APPROVING_PLAYBOOK = "approving_playbook"
    GENERATING_CODE = "generating_code"
    REVIEWING_CODE = "reviewing_code"
    APPLYING_CODE = "applying_code"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class WorkflowCheckpoint:
    """Checkpoint for workflow state persistence."""

    workflow_id: str
    state: WorkflowState
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Artifacts
    project_context: Optional[Dict[str, Any]] = None
    intent: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    materials: Optional[Dict[str, Any]] = None
    mapping: Optional[Dict[str, Any]] = None
    playbook: Optional[Dict[str, Any]] = None
    generated_code: Optional[Dict[str, Any]] = None

    # Error tracking
    error: Optional[str] = None
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "project_context": self.project_context,
            "intent": self.intent,
            "requirements": self.requirements,
            "materials": self.materials,
            "mapping": self.mapping,
            "playbook": self.playbook,
            "generated_code": self.generated_code,
            "error": self.error,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowCheckpoint":
        """Deserialize from dictionary."""
        return cls(
            workflow_id=data["workflow_id"],
            state=WorkflowState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            project_context=data.get("project_context"),
            intent=data.get("intent"),
            requirements=data.get("requirements"),
            materials=data.get("materials"),
            mapping=data.get("mapping"),
            playbook=data.get("playbook"),
            generated_code=data.get("generated_code"),
            error=data.get("error"),
            blocked_reason=data.get("blocked_reason"),
        )


class IntegrationRunner:
    """
    Orchestrates the full dynamic integration workflow.

    Features:
    - Automatic pipeline execution
    - State persistence for resume
    - Blocked state handling
    - Interactive mode support
    """

    def __init__(
        self,
        project_root: Path,
        checkpoint_dir: Optional[Path] = None,
        interactive: bool = True,
        target_dir: Optional[str] = None,
    ):
        """
        Initialize the integration runner.

        Args:
            project_root: Root directory of the project
            checkpoint_dir: Directory for checkpoints (defaults to .processos/)
            interactive: Whether to prompt for user input
            target_dir: Optional subdirectory to limit discovery scope
        """
        self.project_root = Path(project_root)
        self.checkpoint_dir = checkpoint_dir or (self.project_root / ".processos" / "checkpoints")
        self.interactive = interactive
        self.target_dir = target_dir

        # Components
        self.patchset_manager = PatchsetManager(project_root=project_root)
        self.material_collector = MaterialCollector()

        # Event callbacks
        self._callbacks: Dict[str, List[Callable]] = {}

    def run(
        self,
        request: str,
        workflow_id: Optional[str] = None,
    ) -> WorkflowCheckpoint:
        """
        Run the full integration workflow.

        Args:
            request: Natural language integration request
            workflow_id: Optional workflow ID to resume

        Returns:
            WorkflowCheckpoint with final state
        """
        # Initialize or resume checkpoint
        if workflow_id:
            checkpoint = self._load_checkpoint(workflow_id)
        else:
            checkpoint = WorkflowCheckpoint(
                workflow_id=str(uuid.uuid4())[:8],
                state=WorkflowState.INITIALIZED,
            )

        try:
            # Run workflow stages
            checkpoint = self._run_discovery(checkpoint)
            checkpoint = self._run_intent_parsing(checkpoint, request)
            checkpoint = self._run_requirements(checkpoint)
            checkpoint = self._run_material_collection(checkpoint)
            checkpoint = self._run_schema_mapping(checkpoint)
            checkpoint = self._run_playbook_building(checkpoint)
            checkpoint = self._run_code_generation(checkpoint)
            checkpoint = self._run_code_application(checkpoint)

            checkpoint.state = WorkflowState.COMPLETED
            self._emit("workflow_completed", checkpoint)

        except BlockedError as e:
            checkpoint.state = WorkflowState.BLOCKED
            checkpoint.blocked_reason = str(e)
            self._save_checkpoint(checkpoint)
            self._emit("workflow_blocked", checkpoint, e)

        except Exception as e:
            checkpoint.state = WorkflowState.FAILED
            checkpoint.error = str(e)
            self._save_checkpoint(checkpoint)
            self._emit("workflow_failed", checkpoint, e)
            raise

        self._save_checkpoint(checkpoint)
        return checkpoint

    def _run_discovery(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run project discovery stage."""
        if checkpoint.project_context:
            return checkpoint

        checkpoint.state = WorkflowState.DISCOVERING
        self._emit("stage_started", "discovery")

        context = discover_project(self.project_root, target_dir=self.target_dir)
        checkpoint.project_context = context.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "discovery", context)
        return checkpoint

    def _run_intent_parsing(
        self,
        checkpoint: WorkflowCheckpoint,
        request: str,
    ) -> WorkflowCheckpoint:
        """Run intent parsing stage."""
        if checkpoint.intent:
            return checkpoint

        checkpoint.state = WorkflowState.PARSING_INTENT
        self._emit("stage_started", "intent_parsing")

        # Load project context
        context = ProjectContext.from_dict(checkpoint.project_context) if checkpoint.project_context else None

        intent = parse_intent(request, project_context=context)
        checkpoint.intent = intent.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "intent_parsing", intent)
        return checkpoint

    def _run_requirements(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run requirements inference stage."""
        if checkpoint.requirements:
            return checkpoint

        checkpoint.state = WorkflowState.INFERRING_REQUIREMENTS
        self._emit("stage_started", "requirements")

        intent = Intent.from_dict(checkpoint.intent)
        requirements = infer_requirements(intent)
        checkpoint.requirements = requirements.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "requirements", requirements)
        return checkpoint

    def _run_material_collection(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run material collection stage."""
        if checkpoint.materials:
            return checkpoint

        checkpoint.state = WorkflowState.COLLECTING_MATERIALS
        self._emit("stage_started", "material_collection")

        requirements = Requirements.from_dict(checkpoint.requirements)

        # Check if materials are needed
        if not requirements.materials:
            checkpoint.materials = {}
            return checkpoint

        if self.interactive:
            # Interactive collection
            materials = self._collect_materials_interactive(requirements)
        else:
            # Automatic mode - block if materials required
            raise BlockedError("Materials required but running in non-interactive mode")

        checkpoint.materials = materials.to_dict() if hasattr(materials, 'to_dict') else {}
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "material_collection", materials)
        return checkpoint

    def _run_schema_mapping(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run schema mapping stage."""
        if checkpoint.mapping:
            return checkpoint

        checkpoint.state = WorkflowState.MAPPING_SCHEMAS
        self._emit("stage_started", "schema_mapping")

        context = ProjectContext.from_dict(checkpoint.project_context) if checkpoint.project_context else None
        materials = checkpoint.materials or {}

        # Get external schema from materials
        external_schema = materials.get("api_schema", {})
        local_models = context.models if context else []

        if not external_schema:
            # No schema to map - create empty mapping with required fields
            intent_data = checkpoint.intent or {}
            materials_data = checkpoint.materials or {}
            intent_id = f"{intent_data.get('integration_type', 'unknown')}_{intent_data.get('target_service', 'default')}"
            materials_id = materials_data.get("requirements_id", intent_id)
            checkpoint.mapping = {
                "intent_id": intent_id,
                "materials_id": materials_id,
                "field_mappings": [],
                "unmapped_external": [],
                "unmapped_local": [],
            }
            return checkpoint

        mapping = map_schemas(
            external_schema=external_schema,
            local_models=local_models,
            project_context=context,
        )

        if self.interactive:
            checkpoint.state = WorkflowState.REVIEWING_MAPPING
            # Interactive mapping review
            mapper = InteractiveMapper(mapping)
            mapping = self._review_mapping_interactive(mapper)

        checkpoint.mapping = mapping.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "schema_mapping", mapping)
        return checkpoint

    def _run_playbook_building(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run playbook building stage."""
        if checkpoint.playbook:
            return checkpoint

        checkpoint.state = WorkflowState.BUILDING_PLAYBOOK
        self._emit("stage_started", "playbook_building")

        intent = Intent.from_dict(checkpoint.intent)
        requirements = Requirements.from_dict(checkpoint.requirements)
        context = ProjectContext.from_dict(checkpoint.project_context) if checkpoint.project_context else None

        playbook = build_playbook(
            intent=intent,
            requirements=requirements,
            project_context=context,
        )

        if self.interactive:
            checkpoint.state = WorkflowState.APPROVING_PLAYBOOK
            # Get user approval
            if not self._approve_playbook_interactive(playbook):
                raise BlockedError("Playbook not approved by user")
            playbook.approve()

        checkpoint.playbook = playbook.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "playbook_building", playbook)
        return checkpoint

    def _run_code_generation(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run code generation stage."""
        if checkpoint.generated_code:
            return checkpoint

        checkpoint.state = WorkflowState.GENERATING_CODE
        self._emit("stage_started", "code_generation")

        context = ProjectContext.from_dict(checkpoint.project_context) if checkpoint.project_context else None
        intent = Intent.from_dict(checkpoint.intent)
        mapping = SchemaMapping.from_dict(checkpoint.mapping)
        materials = MaterialCollection.from_dict(checkpoint.materials) if checkpoint.materials else MaterialCollection()

        generated = generate_integration_code(
            project_context=context,
            intent=intent,
            mapping=mapping,
            materials=materials,
        )

        if self.interactive:
            checkpoint.state = WorkflowState.REVIEWING_CODE
            # Interactive code review - auto-accept for now until CLI handler is implemented
            generated = self.patchset_manager.review_interactive(generated, auto_accept_all=True)

        checkpoint.generated_code = generated.to_dict()
        checkpoint.updated_at = datetime.now()

        self._emit("stage_completed", "code_generation", generated)
        return checkpoint

    def _run_code_application(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        """Run code application stage."""
        checkpoint.state = WorkflowState.APPLYING_CODE
        self._emit("stage_started", "code_application")

        generated = GeneratedCode.from_dict(checkpoint.generated_code)

        if not generated.all_decided:
            raise BlockedError("Not all generated files have been reviewed")

        # Create and apply patchset
        patchset = self.patchset_manager.create_patchset(generated)
        results = self.patchset_manager.apply_patchset(patchset, create_backup=True)

        self._emit("stage_completed", "code_application", results)
        return checkpoint

    # Interactive helpers

    def _collect_materials_interactive(self, requirements: Requirements) -> MaterialCollection:
        """Interactively collect required materials."""
        self._emit("materials_prompt", requirements)

        # This would be implemented with actual user prompts
        # For now, return empty collection with intent_id as requirements_id
        return MaterialCollection(requirements_id=requirements.intent_id)

    def _review_mapping_interactive(self, mapper: InteractiveMapper) -> SchemaMapping:
        """Interactively review schema mappings."""
        self._emit("mapping_review", mapper)

        # Auto-approve high confidence for now
        mapper.auto_approve_high_confidence()
        return mapper.mapping

    def _approve_playbook_interactive(self, playbook: DynamicPlaybook) -> bool:
        """Get user approval for playbook."""
        self._emit("playbook_approval", playbook)

        # Default to approved for now
        return True

    # Checkpoint persistence

    def _save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> Path:
        """Save checkpoint to disk."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = self.checkpoint_dir / f"{checkpoint.workflow_id}.json"
        path.write_text(json.dumps(checkpoint.to_dict(), indent=2))
        return path

    def _load_checkpoint(self, workflow_id: str) -> WorkflowCheckpoint:
        """Load checkpoint from disk."""
        path = self.checkpoint_dir / f"{workflow_id}.json"
        if not path.exists():
            raise ValueError(f"No checkpoint found for workflow: {workflow_id}")
        data = json.loads(path.read_text())
        return WorkflowCheckpoint.from_dict(data)

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all saved checkpoints."""
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoints.append({
                    "workflow_id": data["workflow_id"],
                    "state": data["state"],
                    "updated_at": data["updated_at"],
                })
            except Exception:
                pass

        return sorted(checkpoints, key=lambda x: x["updated_at"], reverse=True)

    # Event system

    def on(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def _emit(self, event: str, *args) -> None:
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception:
                pass  # Don't let callback errors break the workflow


class BlockedError(Exception):
    """Workflow is blocked waiting for user input."""

    pass
