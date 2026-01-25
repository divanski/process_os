"""
WebSocket message handlers for approval workflow.

Implements:
- T138: APPROVAL_REQUIRED message handler
- T139: APPROVAL message handler
- Integration with ApprovalWorkflow state machine
"""

import json
from typing import Any, Dict, Optional
from uuid import uuid4

from process_os.approval.workflow import ApprovalWorkflow, ReviewSummary


class ApprovalMessageHandler:
    """Handles approval workflow messages via WebSocket."""

    def __init__(self):
        """Initialize approval message handler."""
        self.active_approvals: Dict[str, ApprovalWorkflow] = {}

    def create_approval_required_message(
        self,
        detected_language: str,
        detected_framework: str,
        overall_confidence: float,
        patterns_to_use: list,
        conventions_to_apply: dict,
        potential_issues: list,
        generated_code_preview: str,
    ) -> Dict[str, Any]:
        """
        Create APPROVAL_REQUIRED message (T138).

        Args:
            detected_language: Detected language
            detected_framework: Detected framework
            overall_confidence: Overall confidence score
            patterns_to_use: Patterns to apply
            conventions_to_apply: Conventions to follow
            potential_issues: Potential issues
            generated_code_preview: Preview of generated code

        Returns:
            APPROVAL_REQUIRED message for WebSocket
        """
        # Create unique approval request ID
        approval_request_id = str(uuid4())

        # Create review summary
        review_summary = ReviewSummary(
            detected_language=detected_language,
            detected_framework=detected_framework,
            overall_confidence=overall_confidence,
            patterns_to_use=patterns_to_use,
            conventions_to_apply=conventions_to_apply,
            potential_issues=potential_issues,
            generated_code_preview=generated_code_preview,
        )

        # Create and store workflow
        workflow = ApprovalWorkflow(approval_request_id, review_summary)
        self.active_approvals[approval_request_id] = workflow

        # Build message (T138)
        message = {
            "type": "APPROVAL_REQUIRED",
            "approval_request_id": approval_request_id,
            "review_summary": {
                "detected_language": detected_language,
                "detected_framework": detected_framework,
                "overall_confidence": overall_confidence,
                "patterns_to_use": patterns_to_use,
                "conventions_to_apply": conventions_to_apply,
                "potential_issues": potential_issues,
                "generated_code_preview": generated_code_preview,
            },
        }

        return message

    def handle_approval_message(
        self, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle APPROVAL message from user (T139).

        Args:
            message: APPROVAL message with user decision

        Returns:
            Response message with approval status
        """
        approval_request_id = message.get("approval_request_id")
        action = message.get("action")  # "approve" or "reject"

        if not approval_request_id or not action:
            return {
                "type": "APPROVAL_ERROR",
                "error": "Missing approval_request_id or action",
            }

        # Get workflow
        workflow = self.active_approvals.get(approval_request_id)
        if not workflow:
            return {
                "type": "APPROVAL_ERROR",
                "error": f"Approval request not found: {approval_request_id}",
            }

        # Handle approval (T139)
        if action == "approve":
            reviewer_id = message.get("reviewer_id", "user")
            comment = message.get("comment")

            success = workflow.approve(reviewer_id, comment)

            if success:
                return {
                    "type": "APPROVAL_CONFIRMED",
                    "approval_request_id": approval_request_id,
                    "state": "approved",
                    "reviewer_id": reviewer_id,
                    "comment": comment,
                }
            else:
                return {
                    "type": "APPROVAL_ERROR",
                    "error": "Workflow already decided",
                    "approval_request_id": approval_request_id,
                }

        # Handle rejection (T139)
        elif action == "reject":
            reason = message.get("reason", "No reason provided")

            success = workflow.reject(reason)

            if success:
                return {
                    "type": "APPROVAL_CONFIRMED",
                    "approval_request_id": approval_request_id,
                    "state": "rejected",
                    "reason": reason,
                }
            else:
                return {
                    "type": "APPROVAL_ERROR",
                    "error": "Workflow already decided",
                    "approval_request_id": approval_request_id,
                }

        else:
            return {
                "type": "APPROVAL_ERROR",
                "error": f"Unknown action: {action}",
            }

    def get_workflow(self, approval_request_id: str) -> Optional[ApprovalWorkflow]:
        """
        Get approval workflow.

        Args:
            approval_request_id: Approval request ID

        Returns:
            ApprovalWorkflow if found, None otherwise
        """
        return self.active_approvals.get(approval_request_id)

    def cleanup_expired_approvals(self) -> int:
        """
        Clean up expired approval workflows.

        Returns:
            Number of workflows cleaned up
        """
        import time

        now = time.time()
        expired_ids = []

        for approval_id, workflow in self.active_approvals.items():
            if workflow.is_pending():
                # Calculate how long ago it started
                import datetime

                started = datetime.datetime.fromisoformat(
                    workflow.started_at.rstrip("Z")
                )
                started_timestamp = started.timestamp()
                elapsed = now - started_timestamp

                # If expired, mark for removal
                if elapsed > workflow.approval_timeout_seconds:
                    expired_ids.append(approval_id)

        # Remove expired workflows
        for approval_id in expired_ids:
            del self.active_approvals[approval_id]

        return len(expired_ids)
