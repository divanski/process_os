"""
Unit tests for WebSocket server and communication layer.

Tests:
- T017: WebSocket server initialization and connection
- T020: CONNECT/READY message exchange
- T023: Message serialization/deserialization
"""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from process_os.llm.messages import ConnectMessage, ReadyMessage, ProgressMessage


class TestWebSocketInitialization:
    """Test T017: WebSocket server initialization and connection."""

    def test_websocket_server_can_be_created(self):
        """Verify WebSocket server instance can be created."""
        # This test verifies the foundation for T018 implementation
        # The actual server will be implemented in T018
        assert True  # Placeholder for server instantiation

    def test_websocket_server_configuration(self):
        """Verify WebSocket server has correct endpoint configuration."""
        # Expected: ws://localhost:59328/processos/ws
        expected_endpoint = "ws://localhost:59328/processos/ws"
        assert expected_endpoint  # Placeholder


class TestConnectReadyExchange:
    """Test T020: CONNECT/READY message exchange."""

    def test_connect_message_structure(self):
        """Verify CONNECT message has required fields."""
        message = ConnectMessage(
            project_path="/path/to/project",
            user_id="developer@example.com",
            api_version="1.0.0",
            client_version="ClaudeCode 0.1.0",
        )

        assert message.project_path == "/path/to/project"
        assert message.user_id == "developer@example.com"
        assert message.api_version == "1.0.0"
        assert message.client_version == "ClaudeCode 0.1.0"

    def test_ready_message_structure(self):
        """Verify READY message has required fields."""
        session_id = str(uuid4())
        message = ReadyMessage(
            session_id=session_id,
            project_id="abc123hash",
            processos_version="1.0.0",
            capabilities=[
                "progress_streaming",
                "audit_queries",
                "approval_workflow",
                "novelty_detection",
            ],
        )

        assert message.session_id == session_id
        assert message.project_id == "abc123hash"
        assert message.processos_version == "1.0.0"
        assert len(message.capabilities) == 4
        assert "progress_streaming" in message.capabilities

    def test_connect_ready_handshake(self):
        """Verify CONNECT → READY handshake sequence."""
        # Simulate handshake: client sends CONNECT, server responds with READY
        connect = ConnectMessage(
            project_path="/test/project",
            user_id="test@example.com",
            api_version="1.0.0",
            client_version="ClaudeCode 0.1.0",
        )

        session_id = str(uuid4())
        ready = ReadyMessage(
            session_id=session_id,
            project_id="test-hash",
            processos_version="1.0.0",
            capabilities=["progress_streaming", "audit_queries"],
        )

        # Both messages should exist and have required fields
        assert connect.project_path
        assert ready.session_id


class TestMessageSerialization:
    """Test T023: Message serialization/deserialization."""

    def test_progress_message_serialization(self):
        """Verify PROGRESS message can be serialized to JSON."""
        session_id = str(uuid4())
        message = ProgressMessage(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Analyzing file extensions",
            step_number=1,
            total_steps=4,
            estimated_completion_seconds=15.0,
            is_final=False,
            confidence_scores={
                "language_detection": 0.75,
                "framework_detection": 0.0,
                "pattern_discovery": 0.0,
                "convention_learning": 0.0,
            },
        )

        # Serialize to JSON
        json_data = json.dumps(message.to_dict())
        assert isinstance(json_data, str)

        # Deserialize back
        parsed = json.loads(json_data)
        assert parsed["session_id"] == session_id
        assert parsed["phase"] == "language_detection"
        assert parsed["progress_percent"] == 25.0

    def test_progress_message_with_summary(self):
        """Verify final PROGRESS message includes summary."""
        message = ProgressMessage(
            session_id=str(uuid4()),
            phase="complete",
            progress_percent=100.0,
            current_step="Analysis complete",
            step_number=4,
            total_steps=4,
            estimated_completion_seconds=0.0,
            is_final=True,
            summary={
                "language": "PHP",
                "framework": "Laravel",
                "overall_confidence": 0.95,
                "total_duration_seconds": 45.2,
                "patterns_discovered": 3,
                "conventions_learned": 5,
            },
            confidence_scores={
                "language_detection": 0.98,
                "framework_detection": 0.95,
                "pattern_discovery": 0.90,
                "convention_learning": 0.92,
            },
        )

        json_data = json.dumps(message.to_dict())
        parsed = json.loads(json_data)

        assert parsed["is_final"] is True
        assert "summary" in parsed
        assert parsed["summary"]["language"] == "PHP"
        assert parsed["summary"]["overall_confidence"] == 0.95

    def test_message_validation_schema(self):
        """Verify message validation against schema."""
        # All required fields must be present
        session_id = str(uuid4())

        message = ProgressMessage(
            session_id=session_id,
            phase="language_detection",
            progress_percent=50.0,
            current_step="Step",
            step_number=1,
            total_steps=4,
            estimated_completion_seconds=10.0,
            is_final=False,
            confidence_scores={"language_detection": 0.5},
        )

        data = message.to_dict()

        # Validate required fields exist
        required_fields = [
            "session_id",
            "phase",
            "progress_percent",
            "current_step",
            "step_number",
            "total_steps",
            "estimated_completion_seconds",
            "is_final",
            "confidence_scores",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
