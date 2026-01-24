"""
ProcessOS Bootstrap Module

Bootstraps ProcessOS into host projects with dual-mode Claude instruction pack.
"""

from .bootstrapper import (
    Bootstrapper,
    BootstrapOutput,
    BootstrapResult,
    bootstrap_host,
)
from .command_gateway import (
    CommandGateway,
    CommandGatewayResult,
    execute_command,
)
from .instruction_pack import (
    InstructionPackConfig,
    InstructionPackGenerator,
    generate_instruction_pack,
)

__all__ = [
    # Bootstrapper
    "Bootstrapper",
    "BootstrapResult",
    "BootstrapOutput",
    "bootstrap_host",
    # Command Gateway
    "CommandGateway",
    "CommandGatewayResult",
    "execute_command",
    # Instruction Pack
    "InstructionPackConfig",
    "InstructionPackGenerator",
    "generate_instruction_pack",
]
