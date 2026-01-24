"""
ProcessOS Drift Guard Module

Enforces write allowlist and policy compliance.
"""

from .guard import (
    DriftGuard,
    DriftViolationError,
    WriteViolation,
    GateViolation,
)

__all__ = [
    "DriftGuard",
    "DriftViolationError",
    "WriteViolation",
    "GateViolation",
]
