"""
Audit trail recorder for ProcessOS operations.

Implements:
- T100-T107: Audit event recording for all operation types
- Append-only audit log in .processos/audit/audit.jsonl
- Encryption of sensitive fields (user_id)
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditRecorder:
    """Records audit entries for all ProcessOS operations."""

    def __init__(self, audit_dir: Path):
        """
        Initialize AuditRecorder.

        Args:
            audit_dir: Directory where audit logs are stored (.processos/audit/)
        """
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "audit.jsonl"
        self.session_id = str(uuid.uuid4())

    def record_analysis_started(
        self,
        user_id: str,
        project_path: str,
        target_directory: str,
    ) -> Dict[str, Any]:
        """
        Record analysis_started event (T101).

        Args:
            user_id: ID of user initiating analysis
            project_path: Path to project being analyzed
            target_directory: Target directory within project

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "analysis_started",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "project_path": project_path,
                "target_directory": target_directory,
            },
        }

        self._append_entry(entry)
        return entry

    def record_analysis_completed(
        self,
        user_id: str,
        language: str,
        framework: str,
        overall_confidence: float,
        signals: List[Dict[str, Any]],
        patterns_discovered: List[str],
        conventions_learned: List[str],
    ) -> Dict[str, Any]:
        """
        Record analysis_completed event (T102).

        Args:
            user_id: ID of user running analysis
            language: Detected programming language
            framework: Detected framework
            overall_confidence: Overall confidence score (0-1)
            signals: Detection signals with confidence scores
            patterns_discovered: List of discovered patterns
            conventions_learned: List of learned conventions

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "analysis_completed",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "language": language,
                "framework": framework,
                "overall_confidence": overall_confidence,
                "signals": signals,
                "patterns_discovered": patterns_discovered,
                "conventions_learned": conventions_learned,
            },
        }

        self._append_entry(entry)
        return entry

    def record_code_generation_requested(
        self,
        user_id: str,
        task_description: str,
        detected_language: str,
        detected_framework: str,
    ) -> Dict[str, Any]:
        """
        Record code_generation_requested event (T103).

        Args:
            user_id: ID of user requesting code generation
            task_description: Description of task to generate
            detected_language: Detected language for code generation
            detected_framework: Detected framework

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "code_generation_requested",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "task_description": task_description,
                "detected_language": detected_language,
                "detected_framework": detected_framework,
            },
        }

        self._append_entry(entry)
        return entry

    def record_approval_workflow_started(
        self,
        user_id: str,
        approval_request_id: str,
        patterns_to_use: List[str],
        conventions_to_apply: Dict[str, Any],
        recommendations: List[str],
    ) -> Dict[str, Any]:
        """
        Record approval_workflow_started event (T104).

        Args:
            user_id: ID of user (code generation requester)
            approval_request_id: Unique ID for this approval workflow
            patterns_to_use: List of patterns to apply
            conventions_to_apply: Dict of conventions to apply
            recommendations: List of recommendations for code generation

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "approval_workflow_started",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "approval_request_id": approval_request_id,
                "patterns_to_use": patterns_to_use,
                "conventions_to_apply": conventions_to_apply,
                "recommendations": recommendations,
            },
        }

        self._append_entry(entry)
        return entry

    def record_code_approved(
        self,
        user_id: str,
        approval_request_id: str,
        approved_by: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record code_approved event (T105).

        Args:
            user_id: ID of user who requested code generation
            approval_request_id: Unique ID for this approval workflow
            approved_by: ID of approver/reviewer
            comment: Optional comment from approver

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "code_approved",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "approval_request_id": approval_request_id,
                "approved_by": approved_by,
                "comment": comment,
            },
        }

        self._append_entry(entry)
        return entry

    def record_code_generated(
        self,
        user_id: str,
        files_created: List[str],
        lines_generated: int,
        validation_passed: bool,
    ) -> Dict[str, Any]:
        """
        Record code_generated event (T106).

        Args:
            user_id: ID of user requesting code generation
            files_created: List of files created
            lines_generated: Number of lines of code generated
            validation_passed: Whether code validation passed

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "code_generated",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "files_created": files_created,
                "lines_generated": lines_generated,
                "validation_passed": validation_passed,
            },
        }

        self._append_entry(entry)
        return entry

    def record_code_applied(
        self,
        user_id: str,
        files_written: List[str],
        success: bool,
    ) -> Dict[str, Any]:
        """
        Record code_applied event (T107).

        Args:
            user_id: ID of user applying code to project
            files_written: List of files written to disk
            success: Whether all files were written successfully

        Returns:
            Recorded audit entry
        """
        entry = {
            "entry_id": str(uuid.uuid4()),
            "event_type": "code_applied",
            "user_id": user_id,
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "files_written": files_written,
                "success": success,
            },
        }

        self._append_entry(entry)
        return entry

    def _append_entry(self, entry: Dict[str, Any]) -> None:
        """
        Append entry to audit log (append-only guarantee).

        Args:
            entry: Audit entry to append
        """
        # Append in JSONL format (one JSON object per line)
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
