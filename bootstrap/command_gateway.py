"""
ProcessOS Command Gateway

CLI-first deterministic command execution gateway.
Produces command_id → workspace_id → run_id chain.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from process_os.commands import CommandParser
from process_os.credentials import CredentialProvider
from process_os.drift import DriftGuard, DriftViolationError
from process_os.generators.workspace_generator import WorkspaceGenerator
from process_os.init import ConfigManager
from process_os.init.binding import PROCESSOS_DIR, BindingManager, ProjectBinding
from process_os.runtime.workspace_runner import WorkspaceRunner
from process_os.runtime.integration_runner import IntegrationRunner, WorkflowState, BlockedError
from process_os.stack_fingerprint import StackFingerprint


# Default required credentials for LLM execution
DEFAULT_REQUIRED_CREDENTIALS = ["ANTHROPIC_API_KEY"]


@dataclass
class CommandGatewayResult:
    """Result from command gateway execution."""

    success: bool
    command_id: str = ""
    workspace_id: str = ""
    run_id: str = ""
    run_dir: Optional[Path] = None
    artifacts: List[str] = field(default_factory=list)
    telemetry_file: Optional[Path] = None
    exit_code: int = 0
    error: str = ""
    # Dynamic integration fields
    workflow_state: Optional[str] = None
    generated_files: List[str] = field(default_factory=list)
    checkpoint_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "command_id": self.command_id,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir) if self.run_dir else None,
            "artifacts": self.artifacts,
            "telemetry_file": str(self.telemetry_file) if self.telemetry_file else None,
            "exit_code": self.exit_code,
            "error": self.error,
        }
        if self.workflow_state:
            result["workflow_state"] = self.workflow_state
        if self.generated_files:
            result["generated_files"] = self.generated_files
        if self.checkpoint_path:
            result["checkpoint_path"] = str(self.checkpoint_path)
        return result


class CommandGateway:
    """
    Deterministic command execution gateway.

    Flow:
    1. Parse command → command_id
    2. Load binding/config from host
    3. Verify credentials (T029)
    4. Generate workspace → workspace_id
    5. Execute workspace → run_id
    6. Write outputs to .processos/runs/<run_id>/
    """

    def __init__(self, host_root: Path):
        """
        Initialize command gateway.

        Args:
            host_root: Path to bootstrapped host project
        """
        self.host_root = Path(host_root).resolve()
        self.processos_dir = self.host_root / PROCESSOS_DIR
        self.manager = BindingManager(self.host_root)
        self.config_manager = ConfigManager(self.host_root)
        self.credential_provider: Optional[CredentialProvider] = None

    def _init_credential_provider(self) -> CredentialProvider:
        """Initialize credential provider from config or defaults (T029)."""
        if self.credential_provider:
            return self.credential_provider

        # Try to load sources from unified config
        sources = None
        config = self.config_manager.load()
        if config:
            sources = config.settings.credentials.sources

        self.credential_provider = CredentialProvider(sources=sources)
        return self.credential_provider

    def verify_credentials(
        self,
        required: Optional[List[str]] = None,
    ) -> tuple:
        """
        Verify required credentials are available (T029).

        Args:
            required: List of required credential keys

        Returns:
            Tuple of (success, missing_credentials)
        """
        provider = self._init_credential_provider()
        required = required or DEFAULT_REQUIRED_CREDENTIALS
        missing = []

        for key in required:
            if not provider.has(key):
                missing.append(key)

        return (len(missing) == 0, missing)

    def execute(
        self,
        command: str,
        timestamp: Optional[str] = None,
        dry_run: bool = False,
        skip_credential_check: bool = False,
        use_dynamic: bool = True,
        interactive: bool = False,
        target_dir: Optional[str] = None,
    ) -> CommandGatewayResult:
        """
        Execute a command through the gateway.

        Args:
            command: User command string
            timestamp: Optional fixed timestamp for determinism
            dry_run: Preview execution without running (T033)
            skip_credential_check: Skip credential verification
            use_dynamic: Use IntegrationRunner pipeline (True) or mock agents (False)
            interactive: Enable interactive prompts for user input
            target_dir: Optional subdirectory to limit discovery scope

        Returns:
            CommandGatewayResult with execution details
        """
        # Check if initialized (unified config or legacy)
        config = self.config_manager.load()
        binding = None
        fingerprint = None
        binding_id = ""
        fingerprint_id = ""

        if config:
            binding_id = config.binding_id
            fingerprint_id = config.fingerprint_id
        else:
            if not self.manager.exists():
                return CommandGatewayResult(
                    success=False,
                    exit_code=1,
                    error=f"Project not initialized. Run 'processos init' first.",
                )

            # Load binding and fingerprint
            binding = self.manager.load_binding()
            fingerprint = self.manager.load_fingerprint()

            if not binding or not fingerprint:
                return CommandGatewayResult(
                    success=False,
                    exit_code=1,
                    error="Invalid initialization state: missing binding or fingerprint.",
                )

            binding_id = binding.binding_id
            fingerprint_id = fingerprint.fingerprint_id

        # Verify credentials (T029)
        if not skip_credential_check and not dry_run:
            creds_ok, missing = self.verify_credentials()
            if not creds_ok:
                missing_str = ", ".join(missing)
                return CommandGatewayResult(
                    success=False,
                    exit_code=1,
                    error=f"Missing required credentials: {missing_str}. "
                          f"Set them via environment variables or .env file.",
                )

        # Create drift guard
        policies = {
            "write_allowlist": [".processos/**"],
        }
        drift_guard = DriftGuard(self.host_root, policies.get("write_allowlist"))

        try:
            # Parse command deterministically
            parser = CommandParser()
            task_request = parser.parse(command, include_timestamp=False)

            command_id = task_request.command_id
            workspace_id = task_request.get_workspace_id()

            # Dry run mode: return preview without executing (T033)
            if dry_run:
                return CommandGatewayResult(
                    success=True,
                    command_id=command_id,
                    workspace_id=workspace_id,
                    run_id="(dry-run)",
                    exit_code=0,
                )

            # Set up workspace and run directories
            workspaces_dir = self.processos_dir / "workspaces"
            runs_dir = self.processos_dir / "runs"
            checkpoints_dir = self.processos_dir / "checkpoints"

            # Check write permissions
            drift_guard.check_write(workspaces_dir)
            drift_guard.check_write(runs_dir)
            drift_guard.check_write(checkpoints_dir)

            if use_dynamic:
                # Use IntegrationRunner for real pipeline execution
                return self._execute_dynamic(
                    command=command,
                    command_id=command_id,
                    workspace_id=workspace_id,
                    binding_id=binding_id,
                    fingerprint_id=fingerprint_id,
                    timestamp=timestamp,
                    interactive=interactive,
                    checkpoints_dir=checkpoints_dir,
                    target_dir=target_dir,
                )
            else:
                # Use mock agents (legacy behavior)
                return self._execute_mock(
                    command=command,
                    command_id=command_id,
                    workspace_id=workspace_id,
                    binding_id=binding_id,
                    fingerprint_id=fingerprint_id,
                    timestamp=timestamp,
                    task_request=task_request,
                    workspaces_dir=workspaces_dir,
                )

        except DriftViolationError as e:
            return CommandGatewayResult(
                success=False,
                exit_code=2,
                error=f"Drift violation: {e}",
            )

        except Exception as e:
            return CommandGatewayResult(
                success=False,
                exit_code=3,
                error=f"Execution failed: {e}",
            )

    def _execute_dynamic(
        self,
        command: str,
        command_id: str,
        workspace_id: str,
        binding_id: str,
        fingerprint_id: str,
        timestamp: Optional[str],
        interactive: bool,
        checkpoints_dir: Path,
        target_dir: Optional[str] = None,
    ) -> CommandGatewayResult:
        """
        Execute command using IntegrationRunner pipeline.

        This runs the full dynamic integration workflow:
        Discovery → Intent → Requirements → Mapping → Codegen → Apply
        """
        runner = IntegrationRunner(
            project_root=self.host_root,
            checkpoint_dir=checkpoints_dir,
            interactive=interactive,
            target_dir=target_dir,
        )

        try:
            # Run the integration pipeline
            checkpoint = runner.run(request=command)

            # Collect generated files from checkpoint
            generated_files = []
            if checkpoint.generated_code:
                for file_info in checkpoint.generated_code.get("files", []):
                    if isinstance(file_info, dict) and "path" in file_info:
                        generated_files.append(file_info["path"])
                    elif isinstance(file_info, str):
                        generated_files.append(file_info)

            # Determine run directory from checkpoint
            run_dir = checkpoints_dir / checkpoint.workflow_id
            run_dir.mkdir(parents=True, exist_ok=True)

            # Write trace summary
            self._write_trace_summary(
                run_dir,
                command_id=command_id,
                workspace_id=workspace_id,
                run_id=checkpoint.workflow_id,
                command=command,
                binding_id=binding_id,
                fingerprint_id=fingerprint_id,
                timestamp=timestamp,
            )

            return CommandGatewayResult(
                success=checkpoint.state == WorkflowState.COMPLETED,
                command_id=command_id,
                workspace_id=workspace_id,
                run_id=checkpoint.workflow_id,
                run_dir=run_dir,
                artifacts=[],
                telemetry_file=None,
                exit_code=0 if checkpoint.state == WorkflowState.COMPLETED else 1,
                error=checkpoint.error or "",
                workflow_state=checkpoint.state.value,
                generated_files=generated_files,
                checkpoint_path=checkpoints_dir / f"{checkpoint.workflow_id}.json",
            )

        except BlockedError as e:
            return CommandGatewayResult(
                success=False,
                exit_code=4,
                error=f"Workflow blocked: {e}",
                workflow_state=WorkflowState.BLOCKED.value,
            )

    def _execute_mock(
        self,
        command: str,
        command_id: str,
        workspace_id: str,
        binding_id: str,
        fingerprint_id: str,
        timestamp: Optional[str],
        task_request: Any,
        workspaces_dir: Path,
    ) -> CommandGatewayResult:
        """
        Execute command using mock workspace agents (legacy behavior).
        """
        # Generate workspace
        generator = WorkspaceGenerator(workspaces_root=workspaces_dir)
        workspace = generator.generate(task_request)
        generator.write_workspace(workspace)

        # Run workspace with mock agents
        runner = WorkspaceRunner(workspaces_dir)
        run_state = runner.run(workspace.workspace_id)

        run_id = run_state.run_id
        # Runs are stored under workspaces_root/workspace_id/runs/run_id/
        run_dir = workspaces_dir / workspace.workspace_id / "runs" / run_id

        # Get artifacts
        artifacts = list(run_state.artifacts.keys())

        # Telemetry file
        telemetry_file = run_dir / "telemetry.jsonl"

        # Write trace chain summary
        self._write_trace_summary(
            run_dir,
            command_id=command_id,
            workspace_id=workspace_id,
            run_id=run_id,
            command=command,
            binding_id=binding_id,
            fingerprint_id=fingerprint_id,
            timestamp=timestamp,
        )

        return CommandGatewayResult(
            success=True,
            command_id=command_id,
            workspace_id=workspace_id,
            run_id=run_id,
            run_dir=run_dir,
            artifacts=artifacts,
            telemetry_file=telemetry_file if telemetry_file.exists() else None,
            exit_code=0,
        )

    def _write_trace_summary(
        self,
        run_dir: Path,
        command_id: str,
        workspace_id: str,
        run_id: str,
        command: str,
        binding_id: str,
        fingerprint_id: str,
        timestamp: Optional[str] = None,
    ) -> None:
        """Write trace chain summary file."""
        run_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "trace_chain": {
                "command_id": command_id,
                "workspace_id": workspace_id,
                "run_id": run_id,
            },
            "command": command,
            "binding_id": binding_id,
            "fingerprint_id": fingerprint_id,
            "executed_at": timestamp or datetime.now(timezone.utc).isoformat(),
        }

        summary_file = run_dir / "trace.yaml"
        summary_file.write_text(
            yaml.dump(summary, default_flow_style=False, sort_keys=True),
            encoding="utf-8",
        )


def execute_command(
    host_root: Path,
    command: str,
    timestamp: Optional[str] = None,
    use_dynamic: bool = True,
    interactive: bool = False,
    target_dir: Optional[str] = None,
) -> CommandGatewayResult:
    """
    Convenience function to execute a command.

    Args:
        host_root: Path to bootstrapped host
        command: Command string
        timestamp: Optional fixed timestamp
        use_dynamic: Use IntegrationRunner pipeline (True) or mock agents (False)
        interactive: Enable interactive prompts for user input
        target_dir: Optional subdirectory to limit discovery scope

    Returns:
        CommandGatewayResult
    """
    gateway = CommandGateway(host_root)
    return gateway.execute(
        command,
        timestamp=timestamp,
        use_dynamic=use_dynamic,
        interactive=interactive,
        target_dir=target_dir,
    )
