"""
AsyncWebSocket server for ProcessOS ↔ ClaudeCode real-time communication.

Handles:
- T018: AsyncWebSocketServer implementation
- T019: WebSocket endpoint at ws://localhost:59328/processos/ws
- T021: CONNECT message handler
- T022: READY message construction
- T066: PROGRESS message emission via WebSocket
- T067: Progress update rate limiting integration
"""

import asyncio
import json
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from process_os.llm.messages import (
    ConnectMessage,
    Message,
    ReadyMessage,
    deserialize_message,
)
from process_os.llm.streaming import ProgressStreamManager


class AsyncWebSocketServer:
    """
    Async WebSocket server for bi-directional ProcessOS ↔ ClaudeCode communication.

    Listens on ws://localhost:59328/processos/ws
    Handles session establishment via CONNECT/READY handshake.
    Manages message serialization and routing.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 59328,
        max_connections: int = 100,
        max_message_size: int = 10 * 1024 * 1024,  # 10MB
    ):
        """
        Initialize AsyncWebSocketServer.

        Args:
            host: Server host (default: localhost)
            port: Server port (default: 59328)
            max_connections: Maximum concurrent connections (default: 100)
            max_message_size: Maximum message size in bytes (default: 10MB)
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.max_message_size = max_message_size
        self.endpoint = f"ws://{host}:{port}/processos/ws"

        # Active connections mapping: session_id -> websocket_connection
        self.active_connections: Dict[str, Any] = {}

        # Session metadata: session_id -> session_info
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # Progress streaming managers: session_id -> ProgressStreamManager
        self.progress_managers: Dict[str, ProgressStreamManager] = {}

    async def handle_connect_message(
        self, connect: ConnectMessage, websocket: Any
    ) -> ReadyMessage:
        """
        Handle CONNECT message from client.

        Args:
            connect: CONNECT message from ClaudeCode client
            websocket: WebSocket connection object

        Returns:
            READY message to send back to client
        """
        session_id = str(uuid4())

        # Store session metadata
        self.sessions[session_id] = {
            "session_id": session_id,
            "project_path": connect.project_path,
            "user_id": connect.user_id,
            "client_version": connect.client_version,
            "connected_at": asyncio.get_event_loop().time(),
        }

        # Store active connection
        self.active_connections[session_id] = websocket

        # Create READY response
        ready = ReadyMessage(
            session_id=session_id,
            project_id=self._hash_project_path(connect.project_path),
            processos_version="1.0.0",
            capabilities=[
                "progress_streaming",
                "audit_queries",
                "approval_workflow",
                "novelty_detection",
                "checkpoint_resumption",
                "operation_control",
            ],
        )

        return ready

    async def handle_client_connection(self, websocket: Any, path: str) -> None:
        """
        Handle new client WebSocket connection.

        Args:
            websocket: WebSocket connection object
            path: Connection path (should be /processos/ws)
        """
        try:
            # Wait for CONNECT message
            async for message_data in websocket:
                try:
                    data = json.loads(message_data)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON")
                    continue

                message_type = data.get("type")

                if message_type == "CONNECT":
                    # Deserialize CONNECT message
                    connect = ConnectMessage(
                        project_path=data.get("project_path", ""),
                        user_id=data.get("user_id", ""),
                        api_version=data.get("api_version", "1.0.0"),
                        client_version=data.get("client_version", ""),
                    )

                    # Handle CONNECT and generate READY response
                    ready = await self.handle_connect_message(connect, websocket)

                    # Send READY message
                    await websocket.send(json.dumps(ready.to_dict()))

                    # Now handle further messages for this session
                    session_id = ready.session_id
                    await self._handle_session_messages(
                        websocket, session_id
                    )
                else:
                    await self._send_error(
                        websocket,
                        "First message must be CONNECT",
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Log and close connection on error
            pass
        finally:
            # Clean up session
            for session_id, conn in list(self.active_connections.items()):
                if conn is websocket:
                    del self.active_connections[session_id]
                    if session_id in self.sessions:
                        del self.sessions[session_id]

    async def _handle_session_messages(
        self, websocket: Any, session_id: str
    ) -> None:
        """
        Handle messages after CONNECT/READY handshake complete.

        Args:
            websocket: WebSocket connection object
            session_id: Session identifier
        """
        try:
            async for message_data in websocket:
                try:
                    data = json.loads(message_data)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON")
                    continue

                message_type = data.get("type")

                # Deserialize and handle message based on type
                try:
                    message = deserialize_message(data)
                    # TODO: Route message to appropriate handler
                except ValueError as e:
                    await self._send_error(
                        websocket, f"Unknown message type: {message_type}"
                    )

        except asyncio.CancelledError:
            pass

    async def _send_error(
        self, websocket: Any, error_message: str
    ) -> None:
        """
        Send ERROR message to client.

        Args:
            websocket: WebSocket connection object
            error_message: Error message text
        """
        error_data = {
            "type": "ERROR",
            "error_code": "SERVER_ERROR",
            "error_message": error_message,
        }
        try:
            await websocket.send(json.dumps(error_data))
        except Exception:
            pass

    async def start(self) -> None:
        """Start the WebSocket server and listen for connections."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError(
                "websockets library required. Install with: pip install websockets"
            )

        server = await websockets.serve(
            self.handle_client_connection,
            self.host,
            self.port,
            max_size=self.max_message_size,
        )

        print(f"[OK] WebSocket server started at {self.endpoint}")

        # Keep server running
        await asyncio.Future()

    async def broadcast_message(
        self,
        message: Message,
        exclude_session_id: Optional[str] = None,
    ) -> None:
        """
        Broadcast message to all active connections.

        Args:
            message: Message to broadcast
            exclude_session_id: Optionally exclude one session from broadcast
        """
        message_json = json.dumps(message.to_dict())

        disconnected_sessions = []

        for session_id, websocket in self.active_connections.items():
            if exclude_session_id and session_id == exclude_session_id:
                continue

            try:
                await websocket.send(message_json)
            except Exception:
                # Connection lost, mark for cleanup
                disconnected_sessions.append(session_id)

        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            if session_id in self.active_connections:
                del self.active_connections[session_id]
            if session_id in self.sessions:
                del self.sessions[session_id]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata.

        Args:
            session_id: Session identifier

        Returns:
            Session info dict or None if not found
        """
        return self.sessions.get(session_id)

    def get_active_session_ids(self) -> Set[str]:
        """
        Get all active session IDs.

        Returns:
            Set of active session IDs
        """
        return set(self.active_connections.keys())

    @staticmethod
    def _hash_project_path(project_path: str) -> str:
        """
        Create deterministic hash of project path for project_id.

        Args:
            project_path: Full project path

        Returns:
            Hashed project identifier
        """
        import hashlib

        return hashlib.sha256(project_path.encode()).hexdigest()[:16]

    def create_progress_manager(
        self, session_id: str, operation_id: str
    ) -> ProgressStreamManager:
        """
        Create progress stream manager for a session (T066, T067).

        Args:
            session_id: Session identifier
            operation_id: Associated operation ID

        Returns:
            Created progress manager
        """
        manager = ProgressStreamManager(
            session_id=session_id,
            operation_id=operation_id,
        )

        self.progress_managers[session_id] = manager
        return manager

    def get_progress_manager(
        self, session_id: str
    ) -> Optional[ProgressStreamManager]:
        """
        Get progress manager for session.

        Args:
            session_id: Session identifier

        Returns:
            Progress manager or None if not found
        """
        return self.progress_managers.get(session_id)

    async def emit_progress(
        self,
        session_id: str,
        phase: str,
        progress_percent: float,
        current_step: str,
        step_number: int,
        total_steps: int,
        confidence_scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Emit progress update via WebSocket (T066, T067).

        Respects rate limiting (max 1 per second, 1-2 second average).

        Args:
            session_id: Target session ID
            phase: Analysis phase
            progress_percent: Progress percentage (0-100)
            current_step: Current step description
            step_number: Step number
            total_steps: Total steps
            confidence_scores: Optional explicit confidence scores

        Returns:
            True if emitted, False if rate limited or session not found
        """
        manager = self.get_progress_manager(session_id)
        if not manager:
            return False

        # Update progress (includes rate limiting)
        message = manager.update_progress(
            phase=phase,
            progress_percent=progress_percent,
            current_step=current_step,
            step_number=step_number,
            total_steps=total_steps,
            confidence_scores=confidence_scores,
        )

        # If rate limited, message is empty dict
        if not message:
            return False

        # Send via WebSocket
        return await self.send_to_session(session_id, message)

    async def emit_final_progress(
        self,
        session_id: str,
        language: str,
        framework: str,
        patterns_discovered: int,
        conventions_learned: int,
        overall_confidence: Optional[float] = None,
    ) -> bool:
        """
        Emit final progress summary via WebSocket (T066).

        Args:
            session_id: Target session ID
            language: Detected language
            framework: Detected framework
            patterns_discovered: Number of patterns found
            conventions_learned: Number of conventions learned
            overall_confidence: Optional explicit confidence

        Returns:
            True if sent successfully
        """
        manager = self.get_progress_manager(session_id)
        if not manager:
            return False

        # Emit final summary
        message = manager.emit_final_summary(
            language=language,
            framework=framework,
            patterns_discovered=patterns_discovered,
            conventions_learned=conventions_learned,
            overall_confidence=overall_confidence,
        )

        # Send via WebSocket
        return await self.send_to_session(session_id, message)

    async def send_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """
        Send message to specific session via WebSocket.

        Args:
            session_id: Target session ID
            message: Message dict to send

        Returns:
            True if sent successfully, False if session not found
        """
        if session_id not in self.active_connections:
            return False

        websocket = self.active_connections[session_id]
        message_json = json.dumps(message)

        try:
            await websocket.send(message_json)
            return True
        except Exception:
            # Connection lost, clean up
            if session_id in self.active_connections:
                del self.active_connections[session_id]
            if session_id in self.sessions:
                del self.sessions[session_id]
            if session_id in self.progress_managers:
                del self.progress_managers[session_id]
            return False

    def __repr__(self) -> str:
        """String representation of server."""
        return (
            f"AsyncWebSocketServer(endpoint={self.endpoint}, "
            f"active_connections={len(self.active_connections)}, "
            f"progress_streams={len(self.progress_managers)})"
        )
