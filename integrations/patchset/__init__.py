"""
ProcessOS Patchset Integration

Generates diff/patch files for proposed changes.
Patches are OUTPUT ONLY - never auto-applied.
"""

from .patchset_generator import (
    Patchset,
    PatchEntry,
    PatchsetGenerator,
    generate_patchset,
)

__all__ = [
    "Patchset",
    "PatchEntry",
    "PatchsetGenerator",
    "generate_patchset",
]
