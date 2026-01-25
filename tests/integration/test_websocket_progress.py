"""
Integration tests for WebSocket progress streaming.

Tests:
- T066: PROGRESS message emission via WebSocket
- T067: Progress update rate limiting integration with server
- WebSocket server progress manager integration
"""

import asyncio
import json
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from process_os.llm.server import AsyncWebSocketServer
from process_os.llm.streaming import ProgressStreamManager


class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.closed = False

    async def send(self, message: str):
        """Send message and track it."""
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent_messages.append(json.loads(message))

    async def recv(self):
        """Mock receive - not used in these tests."""
        await asyncio.sleep(1)


class TestWebSocketProgressManagerIntegration:
    """Test WebSocket server progress manager integration (T066, T067)."""

    def test_server_creates_progress_manager(self):
        """Verify server can create progress managers."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        manager = server.create_progress_manager(session_id, operation_id)

        assert manager is not None
        assert isinstance(manager, ProgressStreamManager)
        assert manager.session_id == session_id
        assert manager.operation_id == operation_id

    def test_server_retrieves_progress_manager(self):
        """Verify server can retrieve existing progress managers."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        created_manager = server.create_progress_manager(session_id, operation_id)
        retrieved_manager = server.get_progress_manager(session_id)

        assert retrieved_manager is not None
        assert retrieved_manager.session_id == created_manager.session_id
        assert retrieved_manager.operation_id == created_manager.operation_id

    def test_server_returns_none_for_nonexistent_manager(self):
        """Verify server returns None for unknown session."""
        server = AsyncWebSocketServer()
        manager = server.get_progress_manager("nonexistent-session")
        assert manager is None

    @pytest.mark.asyncio
    async def test_server_emits_progress_message(self):
        """Verify server can emit progress messages via WebSocket (T066)."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Create mock WebSocket connection
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Emit progress
        result = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Analyzing file extensions",
            step_number=1,
            total_steps=4,
            confidence_scores={"language_detection": 0.75},
        )

        assert result is True
        assert len(mock_websocket.sent_messages) == 1

        message = mock_websocket.sent_messages[0]
        assert message["type"] == "PROGRESS"
        assert message["session_id"] == session_id
        assert message["phase"] == "language_detection"
        assert message["progress_percent"] == 25.0

    @pytest.mark.asyncio
    async def test_server_respects_rate_limiting_on_emit_progress(self):
        """Verify server respects rate limiting when emitting progress (T067)."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Create mock WebSocket connection
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Emit first progress message
        result1 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Step 1",
            step_number=1,
            total_steps=4,
        )
        assert result1 is True
        assert len(mock_websocket.sent_messages) == 1

        # Immediately try to emit another message (should be rate limited)
        result2 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=30.0,
            current_step="Step 2",
            step_number=1,
            total_steps=4,
        )

        # Second message should be rate limited (manager.update_progress returns empty dict)
        assert result2 is False
        assert len(mock_websocket.sent_messages) == 1  # Still only 1 message sent

    @pytest.mark.asyncio
    async def test_server_emits_final_progress_summary(self):
        """Verify server can emit final progress summary (T066)."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Create mock WebSocket connection
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Emit final progress
        result = await server.emit_final_progress(
            session_id=session_id,
            language="PHP",
            framework="Laravel",
            patterns_discovered=3,
            conventions_learned=5,
            overall_confidence=0.92,
        )

        assert result is True
        assert len(mock_websocket.sent_messages) == 1

        message = mock_websocket.sent_messages[0]
        assert message["type"] == "PROGRESS"
        assert message["is_final"] is True
        assert message["phase"] == "complete"
        assert message["progress_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_server_handles_connection_loss_during_emit(self):
        """Verify server cleans up on connection loss during emit."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Create mock WebSocket that will fail
        mock_websocket = MockWebSocket()
        mock_websocket.closed = True  # Simulate closed connection
        server.active_connections[session_id] = mock_websocket
        server.sessions[session_id] = {"session_id": session_id}
        server.progress_managers[session_id] = server.create_progress_manager(
            session_id, operation_id
        )

        # Try to emit progress - should fail and clean up
        result = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Step",
            step_number=1,
            total_steps=4,
        )

        # Verify cleanup occurred
        assert result is False
        assert session_id not in server.active_connections
        assert session_id not in server.sessions
        assert session_id not in server.progress_managers

    @pytest.mark.asyncio
    async def test_server_send_to_session_with_dict_message(self):
        """Verify send_to_session works with dict messages."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())

        # Create mock WebSocket
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Send dict message
        message_dict = {
            "type": "TEST",
            "session_id": session_id,
            "data": "test_data",
        }

        result = await server.send_to_session(session_id, message_dict)

        assert result is True
        assert len(mock_websocket.sent_messages) == 1
        assert mock_websocket.sent_messages[0]["type"] == "TEST"

    @pytest.mark.asyncio
    async def test_server_send_to_session_fails_for_unknown_session(self):
        """Verify send_to_session returns False for unknown session."""
        server = AsyncWebSocketServer()

        result = await server.send_to_session(
            "unknown-session", {"type": "TEST"}
        )

        assert result is False


class TestProgressStreamingWorkflow:
    """Test complete progress streaming workflows."""

    @pytest.mark.asyncio
    async def test_complete_analysis_progress_workflow(self):
        """Test complete progress streaming workflow (T066)."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup mock WebSocket
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.sessions[session_id] = {
            "session_id": session_id,
            "project_path": "/test/project",
        }

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Simulate analysis workflow with progress updates
        phases = [
            ("language_detection", 25.0),
            ("framework_detection", 50.0),
            ("pattern_discovery", 75.0),
            ("convention_learning", 90.0),
        ]

        # Emit progress for each phase
        for phase, progress in phases:
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=progress,
                current_step=f"Analyzing {phase}",
                step_number=1,
                total_steps=4,
                confidence_scores={phase: 0.8},
            )
            assert result is True
            # Give rate limiter time to reset
            await asyncio.sleep(1.1)

        # Verify messages were sent (with rate limiting, may not be all phases)
        assert len(mock_websocket.sent_messages) > 0

        # Emit final progress
        result = await server.emit_final_progress(
            session_id=session_id,
            language="Python",
            framework="Django",
            patterns_discovered=5,
            conventions_learned=8,
            overall_confidence=0.87,
        )

        assert result is True

        # Verify final message
        final_message = mock_websocket.sent_messages[-1]
        assert final_message["type"] == "PROGRESS"
        assert final_message["is_final"] is True
        assert final_message["progress_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self):
        """Test progress streaming with multiple concurrent sessions."""
        server = AsyncWebSocketServer()

        sessions = {}
        for i in range(3):
            session_id = str(uuid4())
            operation_id = str(uuid4())

            # Setup for each session
            mock_websocket = MockWebSocket()
            server.active_connections[session_id] = mock_websocket
            server.create_progress_manager(session_id, operation_id)

            sessions[session_id] = {
                "websocket": mock_websocket,
                "operation_id": operation_id,
            }

        # Emit progress for all sessions simultaneously
        tasks = []
        for session_id, info in sessions.items():
            task = server.emit_progress(
                session_id=session_id,
                phase="language_detection",
                progress_percent=25.0,
                current_step="Analyzing",
                step_number=1,
                total_steps=4,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        # Verify each session received message
        for session_id, info in sessions.items():
            assert len(info["websocket"].sent_messages) >= 1

    @pytest.mark.asyncio
    async def test_progress_manager_rate_limiting_respects_1sec_max(self):
        """Verify rate limiting enforces max 1 message per second."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Emit 3 messages rapidly
        result1 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=10.0,
            current_step="Step 1",
            step_number=1,
            total_steps=4,
        )

        result2 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=20.0,
            current_step="Step 2",
            step_number=1,
            total_steps=4,
        )

        result3 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=30.0,
            current_step="Step 3",
            step_number=1,
            total_steps=4,
        )

        # First should succeed, second and third should fail (rate limited)
        assert result1 is True
        assert result2 is False
        assert result3 is False

        # Only 1 message should have been sent
        assert len(mock_websocket.sent_messages) == 1
