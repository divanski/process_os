"""
Storage handler for CodeGenerationSession entities.

Implements:
- T-NEW-007: CodeGenerationSession storage in .processos/sessions/
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class CodeGenerationSession:
    """
    Represents a code generation session with full lifecycle tracking.

    Tracks analysis results, approval status, and generated code.
    """

    def __init__(
        self,
        session_id: str,
        operation_id: str,
        project_path: str,
        user_id: str,
    ):
        """
        Initialize code generation session.

        Args:
            session_id: WebSocket session ID
            operation_id: Associated operation ID
            project_path: Project path
            user_id: User identifier
        """
        self.session_id = session_id
        self.operation_id = operation_id
        self.project_path = project_path
        self.user_id = user_id

        # Session metadata
        self.created_at = datetime.now().isoformat()
        self.status = "active"  # active, analysis_complete, approved, rejected, code_generated

        # Analysis results
        self.analysis_results: Dict[str, Any] = {
            "language": None,
            "framework": None,
            "patterns": [],
            "conventions": [],
            "overall_confidence": 0.0,
        }

        # Approval workflow
        self.approval_status = "pending"  # pending, approved, rejected
        self.approval_by: Optional[str] = None
        self.approval_comment: Optional[str] = None
        self.approval_at: Optional[str] = None

        # Generated code
        self.generated_files: List[Dict[str, Any]] = []
        self.generation_status = "not_started"  # not_started, in_progress, complete, failed

        # Progress tracking
        self.progress_updates: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "project_path": self.project_path,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "status": self.status,
            "analysis_results": self.analysis_results,
            "approval": {
                "status": self.approval_status,
                "approved_by": self.approval_by,
                "comment": self.approval_comment,
                "approved_at": self.approval_at,
            },
            "generated_files": self.generated_files,
            "generation_status": self.generation_status,
            "progress_updates": len(self.progress_updates),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeGenerationSession":
        """Create session from dictionary."""
        session = cls(
            session_id=data["session_id"],
            operation_id=data["operation_id"],
            project_path=data["project_path"],
            user_id=data["user_id"],
        )

        session.created_at = data.get("created_at", session.created_at)
        session.status = data.get("status", session.status)
        session.analysis_results = data.get(
            "analysis_results", session.analysis_results
        )

        approval = data.get("approval", {})
        session.approval_status = approval.get("status", session.approval_status)
        session.approval_by = approval.get("approved_by")
        session.approval_comment = approval.get("comment")
        session.approval_at = approval.get("approved_at")

        session.generated_files = data.get("generated_files", [])
        session.generation_status = data.get(
            "generation_status", session.generation_status
        )

        return session


class SessionStorageManager:
    """
    Manages persistence of CodeGenerationSession objects.

    Stores sessions in .processos/sessions/ directory.
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        """
        Initialize session storage manager.

        Args:
            sessions_dir: Directory for session storage
        """
        self.sessions_dir = Path(sessions_dir) if sessions_dir else Path.cwd()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of sessions
        self.sessions: Dict[str, CodeGenerationSession] = {}

    def create_session(
        self,
        operation_id: str,
        project_path: str,
        user_id: str,
    ) -> CodeGenerationSession:
        """
        Create and store new session.

        Args:
            operation_id: Associated operation ID
            project_path: Project path
            user_id: User identifier

        Returns:
            Created session
        """
        session_id = str(uuid4())
        session = CodeGenerationSession(
            session_id=session_id,
            operation_id=operation_id,
            project_path=project_path,
            user_id=user_id,
        )

        # Store in memory
        self.sessions[session_id] = session

        # Persist to disk
        self._save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[CodeGenerationSession]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session or None if not found
        """
        # Check memory first
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Load from disk
        session_path = self.sessions_dir / f"{session_id}.json"
        if session_path.exists():
            try:
                data = json.loads(session_path.read_text())
                session = CodeGenerationSession.from_dict(data)
                self.sessions[session_id] = session
                return session
            except (json.JSONDecodeError, KeyError):
                return None

        return None

    def update_session(self, session: CodeGenerationSession) -> None:
        """
        Update session.

        Args:
            session: Session to update
        """
        self.sessions[session.session_id] = session
        self._save_session(session)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        # Remove from memory
        if session_id in self.sessions:
            del self.sessions[session_id]

        # Remove from disk
        session_path = self.sessions_dir / f"{session_id}.json"
        if session_path.exists():
            session_path.unlink()
            return True

        return False

    def list_sessions(self) -> List[CodeGenerationSession]:
        """
        List all sessions.

        Returns:
            List of sessions
        """
        sessions = []

        # Scan disk for session files
        for session_file in self.sessions_dir.glob("*.json"):
            session_id = session_file.stem
            session = self.get_session(session_id)
            if session:
                sessions.append(session)

        return sessions

    def get_sessions_for_user(self, user_id: str) -> List[CodeGenerationSession]:
        """
        Get all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of user's sessions
        """
        return [
            session
            for session in self.list_sessions()
            if session.user_id == user_id
        ]

    def get_sessions_for_operation(
        self, operation_id: str
    ) -> List[CodeGenerationSession]:
        """
        Get all sessions for an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            List of operation's sessions
        """
        return [
            session
            for session in self.list_sessions()
            if session.operation_id == operation_id
        ]

    def _save_session(self, session: CodeGenerationSession) -> None:
        """
        Save session to disk.

        Args:
            session: Session to save
        """
        session_path = self.sessions_dir / f"{session.session_id}.json"
        session_path.write_text(json.dumps(session.to_dict(), indent=2))

    def __repr__(self) -> str:
        """String representation."""
        return f"SessionStorageManager(sessions_dir={self.sessions_dir})"
