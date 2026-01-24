"""
ProcessOS Bootstrap

Bootstraps ProcessOS into a host project, creating .processos/ with
binding, fingerprint, and Claude instruction pack.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from process_os.init.binding import (
    PROCESSOS_DIR,
    PROCESSOS_VERSION,
    BindingGenerator,
    BindingManager,
    ProjectBinding,
)
from process_os.stack_fingerprint import (
    FingerprintGenerator,
    StackFingerprint,
)

from .instruction_pack import (
    InstructionPackConfig,
    InstructionPackGenerator,
)


class BootstrapResult(Enum):
    """Result of bootstrap operation."""

    SUCCESS = 0
    ALREADY_BOOTSTRAPPED = 1
    INVALID_HOST = 2
    WRITE_ERROR = 3


@dataclass
class BootstrapOutput:
    """Output from bootstrap operation."""

    result: BootstrapResult
    host_root: Optional[Path] = None
    processos_dir: Optional[Path] = None
    binding_id: str = ""
    fingerprint_id: str = ""
    instruction_pack_files: List[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self):
        return {
            "result": self.result.name,
            "host_root": str(self.host_root) if self.host_root else None,
            "processos_dir": str(self.processos_dir) if self.processos_dir else None,
            "binding_id": self.binding_id,
            "fingerprint_id": self.fingerprint_id,
            "instruction_pack_files": self.instruction_pack_files,
            "message": self.message,
        }


class Bootstrapper:
    """
    Bootstraps ProcessOS into a host project.

    Creates:
    - .processos/binding.yaml
    - .processos/fingerprint.yaml
    - .processos/claude/INSTRUCTIONS.md
    - .processos/claude/CONTRACTS.md
    - .processos/claude/ENTRYPOINT_PROMPT.txt
    - .processos/claude/PROJECT_CONTEXT.json
    """

    def __init__(self, host_root: Path):
        """
        Initialize bootstrapper.

        Args:
            host_root: Path to host project root
        """
        self.host_root = Path(host_root).resolve()
        self.processos_dir = self.host_root / PROCESSOS_DIR
        self.manager = BindingManager(self.host_root)

    def bootstrap(
        self,
        force: bool = False,
        project_name: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> BootstrapOutput:
        """
        Bootstrap ProcessOS into the host project.

        Args:
            force: Overwrite existing bootstrap
            project_name: Optional project name (defaults to directory name)
            timestamp: Optional fixed timestamp for determinism

        Returns:
            BootstrapOutput with result
        """
        # Validate host path
        if not self.host_root.is_dir():
            return BootstrapOutput(
                result=BootstrapResult.INVALID_HOST,
                message=f"Host path does not exist or is not a directory: {self.host_root}",
            )

        # Check for existing bootstrap
        if self.manager.exists() and not force:
            existing_binding = self.manager.load_binding()
            return BootstrapOutput(
                result=BootstrapResult.ALREADY_BOOTSTRAPPED,
                host_root=self.host_root,
                processos_dir=self.processos_dir,
                binding_id=existing_binding.binding_id if existing_binding else "",
                message="Already bootstrapped. Use --force to re-bootstrap.",
            )

        try:
            # Generate fingerprint
            fingerprint_gen = FingerprintGenerator()
            fingerprint = fingerprint_gen.generate(self.host_root, timestamp=timestamp)

            # Generate binding
            binding_gen = BindingGenerator()
            binding = binding_gen.generate(
                fingerprint=fingerprint,
                project_name=project_name,
                timestamp=timestamp,
            )

            # Save fingerprint and binding
            self.manager.save_fingerprint(fingerprint)
            self.manager.save_binding(binding)

            # Generate instruction pack
            pack_config = InstructionPackConfig(
                project_name=binding.project_name,
                host_root=self.host_root,
                fingerprint=fingerprint,
                binding_id=binding.binding_id,
            )

            pack_generator = InstructionPackGenerator(pack_config)
            if timestamp:
                pack_generator.set_timestamp(timestamp)

            claude_dir = self.processos_dir / "claude"
            pack_files = pack_generator.generate(claude_dir)

            return BootstrapOutput(
                result=BootstrapResult.SUCCESS,
                host_root=self.host_root,
                processos_dir=self.processos_dir,
                binding_id=binding.binding_id,
                fingerprint_id=fingerprint.fingerprint_id,
                instruction_pack_files=[f.name for f in pack_files],
                message=f"Successfully bootstrapped ProcessOS in {self.host_root}",
            )

        except Exception as e:
            return BootstrapOutput(
                result=BootstrapResult.WRITE_ERROR,
                host_root=self.host_root,
                message=f"Bootstrap failed: {e}",
            )

    def is_bootstrapped(self) -> bool:
        """Check if host is already bootstrapped."""
        return self.manager.exists()

    def get_binding(self) -> Optional[ProjectBinding]:
        """Get current binding if bootstrapped."""
        return self.manager.load_binding()

    def get_fingerprint(self) -> Optional[StackFingerprint]:
        """Get current fingerprint if bootstrapped."""
        return self.manager.load_fingerprint()


def bootstrap_host(
    host_root: Path,
    force: bool = False,
    project_name: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> BootstrapOutput:
    """
    Convenience function to bootstrap a host project.

    Args:
        host_root: Path to host project
        force: Overwrite existing bootstrap
        project_name: Optional project name
        timestamp: Optional fixed timestamp

    Returns:
        BootstrapOutput
    """
    bootstrapper = Bootstrapper(host_root)
    return bootstrapper.bootstrap(
        force=force,
        project_name=project_name,
        timestamp=timestamp,
    )
