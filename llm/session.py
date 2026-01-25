"""
Session management for ProcessOS WebSocket connections.

Implements:
- T038: SessionManager class
- T039: Session ID generation and tracking
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set
from uuid import uuid4


class SessionManager:
    """
    Manages WebSocket session lifecycle and tracking.

    Tracks:
    - Active sessions with metadata
    - Session creation and access times
    - Session state (connected, disconnected, expired)
    """

    def __init__(self, session_timeout_seconds: int = 3600):
        """
        Initialize SessionManager.

        Args:
            session_timeout_seconds: Inactivity timeout in seconds (default: 1 hour)
        """
        self.session_timeout = timedelta(seconds=session_timeout_seconds)

        # Active sessions: session_id -> session_data
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        project_path: str,
        user_id: str,
        client_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create new session.

        Args:
            project_path: Full path to project
            user_id: User identifier
            client_version: Client version string
            metadata: Optional additional metadata

        Returns:
            Generated session ID (UUID format)
        """
        session_id = str(uuid4())
        now = datetime.now()

        self.sessions[session_id] = {
            "session_id": session_id,
            "project_path": project_path,
            "user_id": user_id,
            "client_version": client_version,
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "status": "active",
            "message_count": 0,
            "metadata": metadata or {},
        }

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Check if session expired
        if self._is_session_expired(session_id):
            self.close_session(session_id)
            return None

        return session

    def update_session_activity(self, session_id: str) -> bool:
        """
        Update session last activity timestamp.

        Args:
            session_id: Session identifier

        Returns:
            True if updated, False if session not found
        """
        if session_id not in self.sessions:
            return False

        self.sessions[session_id]["last_activity"] = datetime.now().isoformat()
        return True

    def increment_message_count(self, session_id: str) -> bool:
        """
        Increment message count for session.

        Args:
            session_id: Session identifier

        Returns:
            True if incremented, False if session not found
        """
        if session_id not in self.sessions:
            return False

        self.sessions[session_id]["message_count"] += 1
        return True

    def close_session(self, session_id: str) -> bool:
        """
        Close session and clean up.

        Args:
            session_id: Session identifier

        Returns:
            True if closed, False if not found
        """
        if session_id not in self.sessions:
            return False

        self.sessions[session_id]["status"] = "closed"
        self.sessions[session_id]["closed_at"] = datetime.now().isoformat()
        # Keep session record for audit, but mark as closed
        return True

    def is_session_active(self, session_id: str) -> bool:
        """
        Check if session is active and not expired.

        Args:
            session_id: Session identifier

        Returns:
            True if session is active
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        if session["status"] != "active":
            return False

        if self._is_session_expired(session_id):
            self.close_session(session_id)
            return False

        return True

    def get_active_sessions(self) -> Set[str]:
        """
        Get all active session IDs.

        Returns:
            Set of active session IDs
        """
        active = set()

        for session_id in list(self.sessions.keys()):
            if self.is_session_active(session_id):
                active.add(session_id)

        return active

    def get_sessions_for_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all sessions for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of sessions for user
        """
        user_sessions = {}

        for session_id, session_data in self.sessions.items():
            if session_data.get("user_id") == user_id:
                user_sessions[session_id] = session_data

        return user_sessions

    def get_sessions_for_project(self, project_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all sessions for a specific project.

        Args:
            project_path: Project path

        Returns:
            Dictionary of sessions for project
        """
        project_sessions = {}

        for session_id, session_data in self.sessions.items():
            if session_data.get("project_path") == project_path:
                project_sessions[session_id] = session_data

        return project_sessions

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from tracking.

        Returns:
            Number of sessions removed
        """
        expired_sessions = []

        for session_id in list(self.sessions.keys()):
            if self._is_session_expired(session_id):
                expired_sessions.append(session_id)

        # Remove expired sessions
        for session_id in expired_sessions:
            del self.sessions[session_id]

        return len(expired_sessions)

    def get_session_count(self) -> int:
        """
        Get total number of active sessions.

        Returns:
            Count of active sessions
        """
        return len(self.get_active_sessions())

    def get_total_sessions(self) -> int:
        """
        Get total number of all sessions (active and closed).

        Returns:
            Count of all sessions
        """
        return len(self.sessions)

    def _is_session_expired(self, session_id: str) -> bool:
        """
        Check if session has expired due to inactivity.

        Args:
            session_id: Session identifier

        Returns:
            True if session is expired
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        if session["status"] != "active":
            return False

        try:
            last_activity = datetime.fromisoformat(session["last_activity"])
            time_since_activity = datetime.now() - last_activity
            return time_since_activity > self.session_timeout
        except (ValueError, TypeError):
            return False

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of session activity.

        Args:
            session_id: Session identifier

        Returns:
            Summary dict or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        try:
            created_at = datetime.fromisoformat(session["created_at"])
            last_activity = datetime.fromisoformat(session["last_activity"])
            duration = last_activity - created_at
        except (ValueError, TypeError):
            duration = timedelta(0)

        return {
            "session_id": session_id,
            "status": session["status"],
            "user_id": session["user_id"],
            "project_path": session["project_path"],
            "message_count": session["message_count"],
            "duration_seconds": duration.total_seconds(),
            "client_version": session["client_version"],
        }

    def __repr__(self) -> str:
        """String representation of session manager."""
        active = len(self.get_active_sessions())
        total = len(self.sessions)
        return f"SessionManager(active={active}, total={total})"
