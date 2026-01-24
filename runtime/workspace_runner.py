"""
ProcessOS Workspace Runner

Executes playbooks within workspaces with full telemetry and state management.

Sprint 9.2: Added workspace locking, atomic attempt counter, idempotency checks.
"""

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional

import yaml


# Blocked reason codes (Sprint 9.2)
class BlockedReasonCode:
    """Machine-readable reason codes for blocked runs."""

    MISSING_MATERIALS = "MISSING_MATERIALS"
    MISSING_SECRETS = "MISSING_SECRETS"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    POLICY_DENIED = "POLICY_DENIED"
    WORKSPACE_LOCKED = "WORKSPACE_LOCKED"

from .artifact_registry import ArtifactRegistry  # noqa: E402
from .context_budgeter import ContextBudgeter  # noqa: E402
from .gate_enforcer import GateEnforcer  # noqa: E402
from .inbox_gate import InboxGate, InboxGateConfig  # noqa: E402
from .task_ledger import TaskLedger  # noqa: E402
from .telemetry import RunStatus, TelemetrySink  # noqa: E402
from .user_stream import UserStream  # noqa: E402


@dataclass
class RunState:
    """State of a workspace run."""

    run_id: str
    workspace_id: str
    command_id: str
    playbook_id: str
    status: str  # running, succeeded, failed, halted, blocked (RunStatus values)
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_step: Optional[str] = None
    failure_reason: Optional[str] = None
    blocked_reason: Optional[str] = None  # For status=blocked (awaiting user materials)
    blocked_gate: Optional[str] = None   # Gate ID that caused block
    blocked_inputs: List[str] = field(default_factory=list)  # Missing inputs list
    blocked_reason_code: Optional[str] = None  # Machine-readable code (Sprint 9.2)
    halt_reason: Optional[str] = None    # For status=halted (system halt)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    blocked_at: Optional[str] = None     # When blocked occurred
    stream_sequence: int = 0             # Last sequence number in STREAM.md
    artifacts: Dict[str, str] = field(default_factory=dict)  # kind -> path
    # Resume lineage (Sprint 9.1)
    resume_attempt: int = 0              # 0=initial run, 1+=resume attempts
    parent_run_id: Optional[str] = None  # Original run in chain (first run)
    resumed_from_run_id: Optional[str] = None  # Immediate predecessor run

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifacts": dict(sorted(self.artifacts.items())),
            "blocked_at": self.blocked_at,
            "blocked_gate": self.blocked_gate,
            "blocked_inputs": sorted(self.blocked_inputs) if self.blocked_inputs else [],
            "blocked_reason": self.blocked_reason,
            "blocked_reason_code": self.blocked_reason_code,
            "command_id": self.command_id,
            "completed_at": self.completed_at,
            "completed_steps": sorted(self.completed_steps),
            "current_step": self.current_step,
            "failed_step": self.failed_step,
            "failure_reason": self.failure_reason,
            "halt_reason": self.halt_reason,
            "parent_run_id": self.parent_run_id,
            "playbook_id": self.playbook_id,
            "resume_attempt": self.resume_attempt,
            "resumed_from_run_id": self.resumed_from_run_id,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "status": self.status,
            "stream_sequence": self.stream_sequence,
            "workspace_id": self.workspace_id,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass
class StepResult:
    """Result of executing a step."""

    step_id: str
    status: str  # completed, failed, skipped
    agent_id: str
    output: Optional[Dict[str, Any]] = None
    artifact_path: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "agent_id": self.agent_id,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "step_id": self.step_id,
        }
        if self.output:
            result["output"] = self.output
        if self.artifact_path:
            result["artifact_path"] = self.artifact_path
        if self.error:
            result["error"] = self.error
        return result


# Type alias for mock agent function
AgentExecutor = Callable[[str, str, Dict[str, Any]], Dict[str, Any]]


class WorkspaceRunner:
    """
    Executes playbooks within workspaces.

    Features:
    - Full telemetry: command_id -> workspace_id -> run_id trace
    - Gate enforcement: halt on failure
    - Artifact tracking: SHA256-addressed storage
    - State management: resumable checkpoints
    """

    def __init__(
        self,
        workspaces_root: Optional[Path] = None,
        agent_executor: Optional[AgentExecutor] = None,
    ):
        """
        Initialize runner.

        Args:
            workspaces_root: Root directory for workspaces
            agent_executor: Function to execute agents (for testing/mocking)
        """
        if workspaces_root is None:
            workspaces_root = Path(__file__).parent.parent / "workspaces"
        self.workspaces_root = Path(workspaces_root)
        self.agent_executor = agent_executor or self._default_agent_executor
        self._lock_fd: Optional[int] = None  # File descriptor for workspace lock

    @contextmanager
    def _workspace_lock(self, workspace_dir: Path) -> Generator[None, None, None]:
        """
        Acquire exclusive lock on workspace (Sprint 9.2).

        Uses file-based locking for cross-platform support.
        Raises ValueError if lock cannot be acquired (workspace already locked).
        """
        lock_path = workspace_dir / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Open/create lock file
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)

        try:
            # Try to acquire exclusive lock (non-blocking)
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                except OSError:
                    os.close(fd)
                    raise ValueError(
                        f"Workspace locked by another process: {workspace_dir.name}"
                    )
            else:
                import fcntl
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    os.close(fd)
                    raise ValueError(
                        f"Workspace locked by another process: {workspace_dir.name}"
                    )

            self._lock_fd = fd
            yield

        finally:
            # Release lock
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)
            self._lock_fd = None

    def _atomic_write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """
        Write JSON atomically using temp file + rename (Sprint 9.2).

        Pattern: write to temp -> fsync -> atomic rename
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, sort_keys=True, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename (cross-platform)
            os.replace(temp_path, str(path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _default_agent_executor(
        self,
        agent_id: str,
        prompt: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Default mock agent executor.

        In production, this would call the actual LLM provider.
        For Sprint 5, returns deterministic mock output.
        """
        return {
            "decision": "proceed",
            "reasoning": f"Mock execution of {agent_id}",
            "artifacts": {
                "result": {
                    "status": "completed",
                    "summary": f"Processed by {agent_id}",
                    "data": inputs,
                }
            },
        }

    def _generate_run_id(self, workspace_id: str, resume_attempt: int) -> str:
        """
        Generate deterministic run ID.

        Sprint 9.1: No randomness. Run ID is derived from workspace_id + resume_attempt.
        Format: run-{workspace_suffix}-a{attempt}
        Example: run-63646f52fc55-a0 (initial), run-63646f52fc55-a1 (first resume)
        """
        workspace_suffix = workspace_id[-12:] if len(workspace_id) > 12 else workspace_id
        return f"run-{workspace_suffix}-a{resume_attempt}"

    def _get_workspace_meta(self, workspace_dir: Path) -> Dict[str, Any]:
        """
        Get workspace metadata from meta.json (Sprint 9.2).

        Returns default metadata if file doesn't exist.
        Also checks for legacy run_metadata.json for migration.
        """
        meta_path = workspace_dir / "meta.json"
        legacy_path = workspace_dir / "run_metadata.json"

        if meta_path.exists():
            with open(meta_path) as f:
                return json.load(f)

        # Check for legacy file and migrate
        if legacy_path.exists():
            with open(legacy_path) as f:
                legacy_data = json.load(f)
            # Migrate to new format
            meta = {
                "next_attempt": legacy_data.get("next_attempt", 0),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_run_id": None,
            }
            self._atomic_write_json(meta_path, meta)
            # Remove legacy file
            legacy_path.unlink()
            return meta

        # Default metadata for new workspace
        return {
            "next_attempt": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_run_id": None,
        }

    def _get_resume_attempt(self, workspace_dir: Path) -> int:
        """Get next resume attempt number from workspace metadata."""
        meta = self._get_workspace_meta(workspace_dir)
        return meta.get("next_attempt", 0)

    def _save_resume_attempt(
        self, workspace_dir: Path, next_attempt: int, run_id: str
    ) -> None:
        """
        Save next resume attempt number atomically (Sprint 9.2).

        Uses atomic write pattern: temp -> fsync -> rename.
        """
        meta = self._get_workspace_meta(workspace_dir)
        meta["next_attempt"] = next_attempt
        meta["last_run_id"] = run_id
        self._atomic_write_json(workspace_dir / "meta.json", meta)

    def _load_playbook(self, workspace_dir: Path) -> Dict[str, Any]:
        """Load playbook from workspace."""
        playbook_path = workspace_dir / "playbook.yaml"
        with open(playbook_path) as f:
            return yaml.safe_load(f)

    def _load_manifest(self, workspace_dir: Path) -> Dict[str, Any]:
        """Load manifest from workspace."""
        manifest_path = workspace_dir / "manifest.yaml"
        with open(manifest_path) as f:
            return yaml.safe_load(f)

    def _load_agent(self, workspace_dir: Path, agent_id: str) -> Dict[str, Any]:
        """Load agent card from workspace."""
        agent_path = workspace_dir / "agents" / f"{agent_id}.yaml"
        with open(agent_path) as f:
            return yaml.safe_load(f)

    def _load_gates(self, workspace_dir: Path) -> List[Dict[str, Any]]:
        """Load gates from workspace."""
        gates_path = workspace_dir / "gates" / "gates.yaml"
        if gates_path.exists():
            with open(gates_path) as f:
                return yaml.safe_load(f) or []
        return []

    def run(
        self,
        workspace_id: str,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        """
        Execute playbook in workspace.

        Args:
            workspace_id: ID of workspace to execute
            initial_input: Initial input data for first step

        Returns:
            Final RunState after execution

        Raises:
            ValueError: If workspace not found or workspace is locked
        """
        workspace_dir = self.workspaces_root / workspace_id
        if not workspace_dir.exists():
            raise ValueError(f"Workspace not found: {workspace_id}")

        # Acquire workspace lock (Sprint 9.2)
        try:
            with self._workspace_lock(workspace_dir):
                return self._run_locked(workspace_dir, workspace_id, initial_input)
        except ValueError as e:
            if "locked" in str(e).lower():
                # Return blocked state for workspace lock conflict
                run_id = f"run-{workspace_id[-12:]}-locked"
                return RunState(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    command_id="",
                    playbook_id="",
                    status=RunStatus.BLOCKED.value,
                    blocked_reason="Workspace locked by another process",
                    blocked_reason_code=BlockedReasonCode.WORKSPACE_LOCKED,
                )
            raise

    def _run_locked(
        self,
        workspace_dir: Path,
        workspace_id: str,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        """Execute playbook while holding workspace lock."""
        # Load workspace artifacts
        manifest = self._load_manifest(workspace_dir)
        playbook = self._load_playbook(workspace_dir)

        # Get resume attempt and generate deterministic run ID (Sprint 9.1)
        resume_attempt = self._get_resume_attempt(workspace_dir)
        run_id = self._generate_run_id(workspace_id, resume_attempt)
        run_dir = workspace_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save incremented resume attempt atomically (Sprint 9.2)
        self._save_resume_attempt(workspace_dir, resume_attempt + 1, run_id)

        # Initialize runtime components
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        artifact_registry = ArtifactRegistry(artifacts_dir)
        context_budgeter = ContextBudgeter()
        gate_enforcer = GateEnforcer(artifact_registry)
        task_ledger = TaskLedger(run_id)
        telemetry = TelemetrySink(run_dir / "telemetry.jsonl")

        # Initialize run state with resume lineage (Sprint 9.1)
        state = RunState(
            run_id=run_id,
            workspace_id=workspace_id,
            command_id=manifest.get("command_id", ""),
            playbook_id=playbook.get("playbook_id", ""),
            status=RunStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc).isoformat(),
            resume_attempt=resume_attempt,
            parent_run_id=None,  # Initial run has no parent
            resumed_from_run_id=None,  # Initial run is not a resume
        )

        # Initialize user stream for this run
        user_stream = UserStream(workspace_dir, run_id, telemetry)

        # Emit run started event
        telemetry.emit(
            "run_started",
            run_id,
            data={
                "workspace_id": workspace_id,
                "command_id": state.command_id,
                "playbook_id": state.playbook_id,
            },
        )

        # Check inbox gates BEFORE running any steps
        # This is the BLOCKED mechanism for awaiting user materials (resumable)
        inbox_gates = playbook.get("inbox_gates", [])
        for inbox_gate_config in inbox_gates:
            gate_id = inbox_gate_config.get("gate_id", "inbox_materials_check")
            integration_id = inbox_gate_config.get("integration_id")

            if integration_id:
                # Derive processos_dir from workspace parent
                processos_dir = workspace_dir.parent.parent  # ws-xxx -> workspaces -> .processos

                config = InboxGateConfig(
                    integration_id=integration_id,
                    required_one_of=inbox_gate_config.get("required_one_of", [
                        "*.postman_collection.json",
                        "openapi.yaml",
                        "openapi.json",
                        "swagger.yaml",
                        "swagger.json",
                        "curl_examples.md",
                        "api_docs.md",
                    ]),
                    require_secrets_file=inbox_gate_config.get("require_secrets_file", True),
                )

                inbox_gate = InboxGate(processos_dir, config)
                result = inbox_gate.check()

                if not result.passed:
                    # Inbox materials missing - BLOCKED (resumable, not failed)
                    user_stream.blocked(
                        "system",
                        f"Awaiting materials for {integration_id.upper()}: {', '.join(result.missing_items)}",
                    )

                    telemetry.emit(
                        "gate_halted",
                        run_id,
                        data={
                            "gate_id": gate_id,
                            "gate_type": "await_inbox_materials",
                            "integration_id": integration_id,
                            "missing_items": result.missing_items,
                            "resume_instructions": result.resume_instructions,
                        },
                    )

                    # Determine reason code (Sprint 9.2)
                    reason_code = BlockedReasonCode.MISSING_MATERIALS
                    if any("secret" in item.lower() for item in result.missing_items):
                        reason_code = BlockedReasonCode.MISSING_SECRETS

                    state.status = RunStatus.BLOCKED.value
                    state.blocked_reason = f"Awaiting materials: {', '.join(result.missing_items)}"
                    state.blocked_gate = gate_id
                    state.blocked_inputs = result.missing_items
                    state.blocked_reason_code = reason_code
                    state.blocked_at = datetime.now(timezone.utc).isoformat()
                    state.stream_sequence = user_stream.get_sequence()

                    # Save state
                    self._save_state(run_dir, state)

                    # Emit run_blocked (terminal but resumable)
                    telemetry.run_blocked(
                        run_id,
                        reason="awaiting_inbox_materials",
                        blocked_at_step="intake",
                        blocked_at_gate=gate_id,
                        missing_inputs=result.missing_items,
                        workspace_id=workspace_id,
                        reason_code=reason_code,
                    )

                    return state

                # Gate passed - materials present
                user_stream.info(
                    "system",
                    f"Materials found for {integration_id.upper()}: {', '.join(result.found_items)}",
                )
                telemetry.emit(
                    "gate_passed",
                    run_id,
                    data={
                        "gate_id": gate_id,
                        "gate_type": "await_inbox_materials",
                        "found_items": result.found_items,
                    },
                )

        # Add tasks to ledger and track entry IDs
        step_entry_ids = {}
        for step in playbook.get("steps", []):
            entry_id = task_ledger.add_requirement(
                step["step_id"],
                f"Execute {step['description']}",
            )
            step_entry_ids[step["step_id"]] = entry_id

        # Execute steps
        steps = sorted(playbook.get("steps", []), key=lambda s: s["sequence"])
        current_input = initial_input or {}

        for step in steps:
            step_id = step["step_id"]
            agent_id = step["agent_id"]

            state.current_step = step_id

            # Emit step started
            telemetry.emit(
                "step_started",
                run_id,
                data={
                    "step_id": step_id,
                    "agent_id": agent_id,
                },
            )

            # Check gates
            step_gates = step.get("gates", [])
            for gate_config in step_gates:
                gate_result = gate_enforcer.evaluate(
                    gate_id=gate_config["gate_id"],
                    gate_type=gate_config["gate_type"],
                    parameters=gate_config.get("parameters", {}),
                    state={"artifacts": []},  # Registry handles artifact lookup
                )

                if not gate_result.passed:
                    # Gate failed - fail execution
                    user_stream.error("system", f"Gate failed: {gate_result.reason}")

                    telemetry.emit(
                        "gate_failed",
                        run_id,
                        data={
                            "step_id": step_id,
                            "gate_id": gate_config["gate_id"],
                            "reason": gate_result.reason,
                        },
                    )

                    state.status = RunStatus.FAILED.value
                    state.failed_step = step_id
                    state.failure_reason = gate_result.reason
                    state.completed_at = datetime.now(timezone.utc).isoformat()
                    state.stream_sequence = user_stream.get_sequence()

                    # Save state and return
                    self._save_state(run_dir, state)
                    telemetry.run_failed(run_id, gate_result.reason, step_id=step_id)
                    return state

                telemetry.emit(
                    "gate_passed",
                    run_id,
                    data={
                        "step_id": step_id,
                        "gate_id": gate_config["gate_id"],
                    },
                )

            # Load agent
            try:
                agent = self._load_agent(workspace_dir, agent_id)
            except FileNotFoundError:
                user_stream.error("system", f"Agent not found: {agent_id}")
                state.status = RunStatus.FAILED.value
                state.failed_step = step_id
                state.failure_reason = f"Agent not found: {agent_id}"
                state.completed_at = datetime.now(timezone.utc).isoformat()
                state.stream_sequence = user_stream.get_sequence()
                self._save_state(run_dir, state)
                telemetry.run_failed(run_id, f"Agent not found: {agent_id}", step_id=step_id)
                return state

            # Emit step start to user stream
            user_stream.info(agent_id, f"Starting {agent.get('name', agent_id)}...")

            # Declare inputs for context budgeter
            input_keys = list(step.get("inputs_spec", {}).keys())
            context_budgeter.declare_inputs(step_id, input_keys)

            # Build agent view (filtered by declared inputs)
            agent_view = {}
            for key in input_keys:
                if key in current_input:
                    agent_view[key] = current_input[key]
                elif key == "raw_input" and "raw_input" not in current_input:
                    # For first step, use initial input
                    agent_view["raw_input"] = json.dumps(initial_input or {})

            # Execute agent
            try:
                prompt = agent.get("prompt_template", "").replace(
                    "{{ input_data }}", json.dumps(agent_view)
                )
                output = self.agent_executor(agent_id, prompt, agent_view)

                # Register artifact
                artifact_kind = f"{agent_id.split('-')[-1]}-output"
                artifact_content = json.dumps(output, sort_keys=True, indent=2)
                artifact_ref = artifact_registry.register(
                    artifact_content,
                    artifact_kind,
                    step_id,
                )

                # Update state with artifact ID (string)
                state.artifacts[artifact_kind] = artifact_ref.artifact_id
                state.completed_steps.append(step_id)

                # Satisfy ledger requirement
                entry_id = step_entry_ids.get(step_id)
                if entry_id:
                    task_ledger.satisfy(entry_id, artifact_ref.sha256)

                # Prepare input for next step
                current_input = {
                    "previous_output": output,
                    **current_input,
                }

                telemetry.emit(
                    "step_completed",
                    run_id,
                    data={
                        "step_id": step_id,
                        "agent_id": agent_id,
                        "artifact_id": artifact_ref.artifact_id,
                    },
                )

            except Exception as e:
                user_stream.error(agent_id, f"Step failed: {str(e)}")
                state.status = RunStatus.FAILED.value
                state.failed_step = step_id
                state.failure_reason = str(e)
                state.completed_at = datetime.now(timezone.utc).isoformat()
                state.stream_sequence = user_stream.get_sequence()

                entry_id = step_entry_ids.get(step_id)
                if entry_id:
                    task_ledger.fail(entry_id, str(e))

                telemetry.emit(
                    "step_failed",
                    run_id,
                    data={
                        "step_id": step_id,
                        "agent_id": agent_id,
                        "error": str(e),
                    },
                )

                self._save_state(run_dir, state)
                self._save_ledger(run_dir, task_ledger)
                telemetry.run_failed(run_id, str(e), step_id=step_id)
                return state

            # Step completed successfully
            user_stream.success(agent_id, f"Completed {agent.get('name', agent_id)}")

        # All steps completed successfully
        user_stream.success("system", f"Run completed successfully ({len(state.completed_steps)} steps)")
        state.status = RunStatus.SUCCEEDED.value
        state.current_step = None
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.stream_sequence = user_stream.get_sequence()

        telemetry.run_succeeded(
            run_id,
            steps_completed=len(state.completed_steps),
            artifacts_count=len(state.artifacts),
        )

        self._save_state(run_dir, state)
        self._save_ledger(run_dir, task_ledger)

        return state

    def _save_state(self, run_dir: Path, state: RunState) -> None:
        """Save run state to disk."""
        state_path = run_dir / "state.json"
        state_path.write_text(state.to_json())

    def _save_ledger(self, run_dir: Path, ledger: TaskLedger) -> None:
        """Save task ledger to disk."""
        ledger_path = run_dir / "ledger.json"
        ledger_data = {
            "entries": [e.to_dict() for e in ledger._entries],
        }
        ledger_path.write_text(json.dumps(ledger_data, sort_keys=True, indent=2))

    def get_run_state(self, workspace_id: str, run_id: str) -> Optional[RunState]:
        """
        Load run state from disk.

        Args:
            workspace_id: Workspace identifier
            run_id: Run identifier

        Returns:
            RunState if found, None otherwise
        """
        run_dir = self.workspaces_root / workspace_id / "runs" / run_id
        state_path = run_dir / "state.json"

        if not state_path.exists():
            return None

        with open(state_path) as f:
            data = json.load(f)

        return RunState(
            run_id=data["run_id"],
            workspace_id=data["workspace_id"],
            command_id=data["command_id"],
            playbook_id=data["playbook_id"],
            status=data["status"],
            current_step=data.get("current_step"),
            completed_steps=data.get("completed_steps", []),
            failed_step=data.get("failed_step"),
            failure_reason=data.get("failure_reason"),
            blocked_reason=data.get("blocked_reason"),
            blocked_gate=data.get("blocked_gate"),
            blocked_inputs=data.get("blocked_inputs", []),
            blocked_reason_code=data.get("blocked_reason_code"),
            halt_reason=data.get("halt_reason"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            blocked_at=data.get("blocked_at"),
            stream_sequence=data.get("stream_sequence", 0),
            artifacts=data.get("artifacts", {}),
            # Resume lineage fields (Sprint 9.1)
            resume_attempt=data.get("resume_attempt", 0),
            parent_run_id=data.get("parent_run_id"),
            resumed_from_run_id=data.get("resumed_from_run_id"),
        )

    def list_runs(self, workspace_id: str) -> List[str]:
        """List all runs in workspace."""
        runs_dir = self.workspaces_root / workspace_id / "runs"
        if not runs_dir.exists():
            return []

        return sorted([
            d.name for d in runs_dir.iterdir()
            if d.is_dir() and d.name.startswith("run-")
        ])

    def get_latest_run(self, workspace_id: str) -> Optional[RunState]:
        """Get the most recent run for a workspace."""
        runs = self.list_runs(workspace_id)
        if not runs:
            return None
        return self.get_run_state(workspace_id, runs[-1])

    def resume(
        self,
        workspace_id: str,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        """
        Resume a blocked run.

        Args:
            workspace_id: ID of workspace to resume
            initial_input: Optional input data

        Returns:
            Final RunState after execution

        Raises:
            ValueError: If workspace not found or run not resumable
        """
        workspace_dir = self.workspaces_root / workspace_id
        if not workspace_dir.exists():
            raise ValueError(f"Workspace not found: {workspace_id}")

        # Get latest run state (before lock to check resumability)
        latest_state = self.get_latest_run(workspace_id)
        if latest_state is None:
            raise ValueError(f"No runs found for workspace: {workspace_id}")

        # Check if resumable
        if latest_state.status != RunStatus.BLOCKED.value:
            raise ValueError(
                f"Run not resumable: status is '{latest_state.status}', expected 'blocked'"
            )

        # Acquire workspace lock (Sprint 9.2)
        try:
            with self._workspace_lock(workspace_dir):
                return self._resume_locked(
                    workspace_dir, workspace_id, latest_state, initial_input
                )
        except ValueError as e:
            if "locked" in str(e).lower():
                # Return blocked state for workspace lock conflict
                run_id = f"run-{workspace_id[-12:]}-locked"
                return RunState(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    command_id="",
                    playbook_id="",
                    status=RunStatus.BLOCKED.value,
                    blocked_reason="Workspace locked by another process",
                    blocked_reason_code=BlockedReasonCode.WORKSPACE_LOCKED,
                )
            raise

    def _resume_locked(
        self,
        workspace_dir: Path,
        workspace_id: str,
        latest_state: RunState,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> RunState:
        """Resume blocked run while holding workspace lock."""
        # Load workspace artifacts
        manifest = self._load_manifest(workspace_dir)
        playbook = self._load_playbook(workspace_dir)

        # Get resume attempt and generate deterministic run ID (Sprint 9.1)
        resume_attempt = self._get_resume_attempt(workspace_dir)
        run_id = self._generate_run_id(workspace_id, resume_attempt)
        run_dir = workspace_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save incremented resume attempt atomically (Sprint 9.2)
        self._save_resume_attempt(workspace_dir, resume_attempt + 1, run_id)

        # Determine parent run (first run in the chain)
        parent_run_id = latest_state.parent_run_id or latest_state.run_id

        # Initialize runtime components
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        artifact_registry = ArtifactRegistry(artifacts_dir)
        context_budgeter = ContextBudgeter()
        gate_enforcer = GateEnforcer(artifact_registry)
        task_ledger = TaskLedger(run_id)
        telemetry = TelemetrySink(run_dir / "telemetry.jsonl")

        # Initialize run state with resume lineage (Sprint 9.1)
        state = RunState(
            run_id=run_id,
            workspace_id=workspace_id,
            command_id=manifest.get("command_id", ""),
            playbook_id=playbook.get("playbook_id", ""),
            status=RunStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc).isoformat(),
            resume_attempt=resume_attempt,
            parent_run_id=parent_run_id,
            resumed_from_run_id=latest_state.run_id,
        )

        # Initialize user stream, continuing sequence from previous run
        user_stream = UserStream(workspace_dir, run_id, telemetry)
        user_stream.set_sequence(latest_state.stream_sequence)

        # Emit run resumed event with lineage (Sprint 9.1)
        telemetry.run_resumed(
            run_id,
            resumed_from_step=latest_state.blocked_gate or "unknown",
            previous_status=latest_state.status,
            from_run_id=latest_state.run_id,
            parent_run_id=parent_run_id,
            resume_attempt=resume_attempt,
        )
        user_stream.info("system", "Resuming run from blocked state...")

        # Re-check inbox gates
        inbox_gates = playbook.get("inbox_gates", [])
        for inbox_gate_config in inbox_gates:
            gate_id = inbox_gate_config.get("gate_id", "inbox_materials_check")
            integration_id = inbox_gate_config.get("integration_id")

            if integration_id:
                processos_dir = workspace_dir.parent.parent

                config = InboxGateConfig(
                    integration_id=integration_id,
                    required_one_of=inbox_gate_config.get("required_one_of", [
                        "*.postman_collection.json",
                        "openapi.yaml",
                        "openapi.json",
                        "swagger.yaml",
                        "swagger.json",
                        "curl_examples.md",
                        "api_docs.md",
                    ]),
                    require_secrets_file=inbox_gate_config.get("require_secrets_file", True),
                )

                inbox_gate = InboxGate(processos_dir, config)
                result = inbox_gate.check()

                if not result.passed:
                    # Still blocked
                    user_stream.blocked(
                        "system",
                        f"Still awaiting materials for {integration_id.upper()}: {', '.join(result.missing_items)}",
                    )

                    # Determine reason code (Sprint 9.2)
                    reason_code = BlockedReasonCode.MISSING_MATERIALS
                    if any("secret" in item.lower() for item in result.missing_items):
                        reason_code = BlockedReasonCode.MISSING_SECRETS

                    state.status = RunStatus.BLOCKED.value
                    state.blocked_reason = f"Awaiting materials: {', '.join(result.missing_items)}"
                    state.blocked_gate = gate_id
                    state.blocked_inputs = result.missing_items
                    state.blocked_reason_code = reason_code
                    state.blocked_at = datetime.now(timezone.utc).isoformat()
                    state.stream_sequence = user_stream.get_sequence()

                    self._save_state(run_dir, state)
                    telemetry.run_blocked(
                        run_id,
                        reason="awaiting_inbox_materials",
                        blocked_at_step="intake",
                        blocked_at_gate=gate_id,
                        missing_inputs=result.missing_items,
                        workspace_id=workspace_id,
                        reason_code=reason_code,
                    )
                    return state

                # Gate now passes
                user_stream.success(
                    "system",
                    f"Materials found for {integration_id.upper()}: {', '.join(result.found_items)}",
                )
                telemetry.emit(
                    "gate_passed",
                    run_id,
                    data={
                        "gate_id": gate_id,
                        "gate_type": "await_inbox_materials",
                        "found_items": result.found_items,
                    },
                )

        # Continue with normal run execution (all gates passed)
        # This duplicates some code from run() but keeps the flow clear
        step_entry_ids = {}
        for step in playbook.get("steps", []):
            entry_id = task_ledger.add_requirement(
                step["step_id"],
                f"Execute {step['description']}",
            )
            step_entry_ids[step["step_id"]] = entry_id

        steps = sorted(playbook.get("steps", []), key=lambda s: s["sequence"])
        current_input = initial_input or {}

        for step in steps:
            step_id = step["step_id"]
            agent_id = step["agent_id"]

            state.current_step = step_id

            telemetry.emit(
                "step_started",
                run_id,
                data={"step_id": step_id, "agent_id": agent_id},
            )

            # Check gates
            step_gates = step.get("gates", [])
            for gate_config in step_gates:
                gate_result = gate_enforcer.evaluate(
                    gate_id=gate_config["gate_id"],
                    gate_type=gate_config["gate_type"],
                    parameters=gate_config.get("parameters", {}),
                    state={"artifacts": []},
                )

                if not gate_result.passed:
                    user_stream.error("system", f"Gate failed: {gate_result.reason}")
                    telemetry.emit(
                        "gate_failed",
                        run_id,
                        data={
                            "step_id": step_id,
                            "gate_id": gate_config["gate_id"],
                            "reason": gate_result.reason,
                        },
                    )

                    state.status = RunStatus.FAILED.value
                    state.failed_step = step_id
                    state.failure_reason = gate_result.reason
                    state.completed_at = datetime.now(timezone.utc).isoformat()
                    state.stream_sequence = user_stream.get_sequence()

                    self._save_state(run_dir, state)
                    telemetry.run_failed(run_id, gate_result.reason, step_id=step_id)
                    return state

                telemetry.emit(
                    "gate_passed",
                    run_id,
                    data={"step_id": step_id, "gate_id": gate_config["gate_id"]},
                )

            # Load and execute agent
            try:
                agent = self._load_agent(workspace_dir, agent_id)
            except FileNotFoundError:
                user_stream.error("system", f"Agent not found: {agent_id}")
                state.status = RunStatus.FAILED.value
                state.failed_step = step_id
                state.failure_reason = f"Agent not found: {agent_id}"
                state.completed_at = datetime.now(timezone.utc).isoformat()
                state.stream_sequence = user_stream.get_sequence()
                self._save_state(run_dir, state)
                telemetry.run_failed(run_id, f"Agent not found: {agent_id}", step_id=step_id)
                return state

            user_stream.info(agent_id, f"Starting {agent.get('name', agent_id)}...")

            input_keys = list(step.get("inputs_spec", {}).keys())
            context_budgeter.declare_inputs(step_id, input_keys)

            agent_view = {}
            for key in input_keys:
                if key in current_input:
                    agent_view[key] = current_input[key]
                elif key == "raw_input" and "raw_input" not in current_input:
                    agent_view["raw_input"] = json.dumps(initial_input or {})

            try:
                prompt = agent.get("prompt_template", "").replace(
                    "{{ input_data }}", json.dumps(agent_view)
                )
                output = self.agent_executor(agent_id, prompt, agent_view)

                artifact_kind = f"{agent_id.split('-')[-1]}-output"
                artifact_content = json.dumps(output, sort_keys=True, indent=2)
                artifact_ref = artifact_registry.register(
                    artifact_content,
                    artifact_kind,
                    step_id,
                )

                state.artifacts[artifact_kind] = artifact_ref.artifact_id
                state.completed_steps.append(step_id)

                entry_id = step_entry_ids.get(step_id)
                if entry_id:
                    task_ledger.satisfy(entry_id, artifact_ref.sha256)

                current_input = {"previous_output": output, **current_input}

                telemetry.emit(
                    "step_completed",
                    run_id,
                    data={
                        "step_id": step_id,
                        "agent_id": agent_id,
                        "artifact_id": artifact_ref.artifact_id,
                    },
                )

                user_stream.success(agent_id, f"Completed {agent.get('name', agent_id)}")

            except Exception as e:
                user_stream.error(agent_id, f"Step failed: {str(e)}")
                state.status = RunStatus.FAILED.value
                state.failed_step = step_id
                state.failure_reason = str(e)
                state.completed_at = datetime.now(timezone.utc).isoformat()
                state.stream_sequence = user_stream.get_sequence()

                entry_id = step_entry_ids.get(step_id)
                if entry_id:
                    task_ledger.fail(entry_id, str(e))

                telemetry.emit(
                    "step_failed",
                    run_id,
                    data={"step_id": step_id, "agent_id": agent_id, "error": str(e)},
                )

                self._save_state(run_dir, state)
                self._save_ledger(run_dir, task_ledger)
                telemetry.run_failed(run_id, str(e), step_id=step_id)
                return state

        # All steps completed successfully
        user_stream.success("system", f"Run completed successfully ({len(state.completed_steps)} steps)")
        state.status = RunStatus.SUCCEEDED.value
        state.current_step = None
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.stream_sequence = user_stream.get_sequence()

        telemetry.run_succeeded(
            run_id,
            steps_completed=len(state.completed_steps),
            artifacts_count=len(state.artifacts),
        )

        self._save_state(run_dir, state)
        self._save_ledger(run_dir, task_ledger)

        return state
