"""
Audit Trail and Decision History Module for ProcessOS CI/CL Client Integration

This module provides:
- Append-only audit trail storage with JSON indexes
- Audit entry recording and querying
- Role-based access control (DEVELOPER/TEAM_LEAD/ADMIN)
- Encryption for sensitive fields
"""

from .types import AuditEntry, ProjectAuditTrail
from .recorder import AuditRecorder
from .query import AuditQuery

__all__ = [
    "AuditEntry",
    "ProjectAuditTrail",
    "AuditRecorder",
    "AuditQuery",
]
