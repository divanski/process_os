"""
Approval Workflow Module for ProcessOS CI/CL Client Integration

This module provides:
- State machine for approval workflow (pending → approved/rejected)
- Review summary with architecture analysis results
- Integration with ClaudeCode modal dialog
- Conflict detection and warning system
"""

from .workflow import ApprovalWorkflow, ReviewSummary
from .formatter import ReviewSummaryFormatter

__all__ = [
    "ApprovalWorkflow",
    "ReviewSummary",
    "ReviewSummaryFormatter",
]
