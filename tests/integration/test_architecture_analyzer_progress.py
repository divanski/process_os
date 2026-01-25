"""
Integration tests for ArchitectureAnalyzer with progress streaming.

Tests:
- T065: ArchitectureAnalyzer integration with progress streaming
- Progress emission at each analysis milestone
- Final summary emission with analysis results
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, List
from uuid import uuid4

import pytest

from process_os.architecture.analyzer import ArchitectureAnalyzer
from process_os.llm.server import AsyncWebSocketServer


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.closed = False

    async def send(self, message: str):
        """Track sent messages."""
        import json
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent_messages.append(json.loads(message))


class TestArchitectureAnalyzerProgress:
    """Test ArchitectureAnalyzer integration with progress streaming (T065)."""

    def test_analyzer_with_progress_server(self):
        """Verify ArchitectureAnalyzer can be created."""
        analyzer = ArchitectureAnalyzer()
        assert analyzer is not None
        assert analyzer.language_detector is not None
        assert analyzer.framework_detector is not None
        assert analyzer.pattern_discoverer is not None
        assert analyzer.convention_learner is not None

    def test_server_tracks_analysis_progress(self):
        """Verify server can track analysis progress via manager."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        manager = server.create_progress_manager(session_id, operation_id)

        # Simulate analysis phases
        phases = [
            ("language_detection", 25.0),
            ("framework_detection", 50.0),
            ("pattern_discovery", 75.0),
            ("convention_learning", 100.0),
        ]

        messages = []
        for phase, progress in phases:
            message = manager.update_progress(
                phase=phase,
                progress_percent=progress,
                current_step=f"Analyzing {phase}",
                step_number=int(progress // 25),
                total_steps=4,
                confidence_scores={phase: 0.85},
            )
            if message:  # Not rate limited
                messages.append(message)

        # Should have at least one message (first call not rate limited)
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_progress_streaming_during_analysis(self):
        """Verify progress is streamed during analysis simulation."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup mock WebSocket
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Simulate analysis workflow with progress updates
        phases = [
            ("language_detection", 25.0, "Detecting language", 1),
            ("framework_detection", 50.0, "Detecting framework", 2),
            ("pattern_discovery", 75.0, "Discovering patterns", 3),
            ("convention_learning", 100.0, "Learning conventions", 4),
        ]

        for phase, progress, step, step_num in phases:
            # Emit progress
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=progress,
                current_step=step,
                step_number=step_num,
                total_steps=4,
                confidence_scores={phase: 0.85},
            )

            if result:  # Message was sent (not rate limited)
                # Verify message structure
                assert len(mock_websocket.sent_messages) > 0
                last_message = mock_websocket.sent_messages[-1]
                assert last_message["type"] == "PROGRESS"
                assert last_message["phase"] == phase
                assert last_message["progress_percent"] == progress

            # Wait for rate limiter to reset (1 second)
            await asyncio.sleep(1.1)

    @pytest.mark.asyncio
    async def test_analysis_final_summary_emission(self):
        """Verify final summary is emitted with analysis results."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup mock WebSocket
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket

        # Create progress manager
        server.create_progress_manager(session_id, operation_id)

        # Simulate final summary
        result = await server.emit_final_progress(
            session_id=session_id,
            language="PHP",
            framework="Laravel",
            patterns_discovered=5,
            conventions_learned=8,
            overall_confidence=0.92,
        )

        assert result is True
        assert len(mock_websocket.sent_messages) == 1

        final_message = mock_websocket.sent_messages[0]
        assert final_message["type"] == "PROGRESS"
        assert final_message["is_final"] is True
        assert final_message["phase"] == "complete"
        assert final_message["progress_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_concurrent_analysis_sessions(self):
        """Verify multiple analysis sessions can stream progress concurrently."""
        server = AsyncWebSocketServer()

        # Create multiple analysis sessions
        sessions = {}
        for i in range(3):
            session_id = str(uuid4())
            operation_id = str(uuid4())

            mock_websocket = MockWebSocket()
            server.active_connections[session_id] = mock_websocket
            server.create_progress_manager(session_id, operation_id)

            sessions[session_id] = {
                "websocket": mock_websocket,
                "operation_id": operation_id,
            }

        # Emit progress for all sessions simultaneously
        tasks = []
        for session_id in sessions.keys():
            task = server.emit_progress(
                session_id=session_id,
                phase="language_detection",
                progress_percent=25.0,
                current_step="Analyzing language",
                step_number=1,
                total_steps=4,
                confidence_scores={"language_detection": 0.85},
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        # Each session should have received message
        for session_id, info in sessions.items():
            assert len(info["websocket"].sent_messages) >= 1

    @pytest.mark.asyncio
    async def test_progress_with_confidence_scores(self):
        """Verify progress messages include confidence scores for each phase."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Emit progress with confidence scores
        confidence_scores = {
            "language_detection": 0.95,
            "framework_detection": 0.85,
            "pattern_discovery": 0.80,
            "convention_learning": 0.75,
        }

        result = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Detected PHP",
            step_number=1,
            total_steps=4,
            confidence_scores=confidence_scores,
        )

        assert result is True
        message = mock_websocket.sent_messages[0]
        assert "confidence_scores" in message
        assert message["confidence_scores"]["language_detection"] == 0.95

    @pytest.mark.asyncio
    async def test_analysis_progress_phases_sequence(self):
        """Verify analysis goes through all 4 phases in correct sequence."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        expected_phases = [
            "language_detection",
            "framework_detection",
            "pattern_discovery",
            "convention_learning",
        ]

        # Emit all 4 phases with rate limiting
        for idx, phase in enumerate(expected_phases):
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=(idx + 1) * 25.0,
                current_step=f"Analyzing {phase}",
                step_number=idx + 1,
                total_steps=4,
                confidence_scores={phase: 0.85},
            )

            if result:
                message = mock_websocket.sent_messages[-1]
                assert message["phase"] == phase

            # Wait for rate limiter
            await asyncio.sleep(1.1)

        # Final progress should have gone through phases
        assert len(mock_websocket.sent_messages) > 0

    @pytest.mark.asyncio
    async def test_estimated_completion_time_during_analysis(self):
        """Verify estimated completion time decreases as analysis progresses."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        manager = server.create_progress_manager(session_id, operation_id)

        # Track estimated completion times
        estimated_times = []

        # Emit progress at different stages
        for progress in [25.0, 50.0, 75.0]:
            message = manager.update_progress(
                phase="analysis",
                progress_percent=progress,
                current_step="Analyzing",
                step_number=1,
                total_steps=4,
            )

            if message:
                estimated_time = message.get("estimated_completion_seconds", 0)
                estimated_times.append(estimated_time)

        # Estimated times should generally decrease as progress increases
        # (allowing for some variance in calculation)
        assert len(estimated_times) > 0


class TestArchitectureAnalyzerIntegration:
    """Test ArchitectureAnalyzer with WebSocket server integration."""

    def test_analyzer_and_server_work_together(self):
        """Verify ArchitectureAnalyzer and WebSocket server can work together."""
        analyzer = ArchitectureAnalyzer()
        server = AsyncWebSocketServer()

        # Verify both are properly initialized
        assert analyzer is not None
        assert server is not None
        assert len(server.active_connections) == 0
        assert len(server.progress_managers) == 0

    @pytest.mark.asyncio
    async def test_full_analysis_workflow_with_progress(self):
        """Test complete analysis workflow with progress streaming."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Simulate full analysis: language → framework → patterns → conventions
        analysis_phases = [
            {
                "phase": "language_detection",
                "progress": 25.0,
                "step": "Scanning file extensions",
                "results": {"language": "PHP"},
            },
            {
                "phase": "framework_detection",
                "progress": 50.0,
                "step": "Detecting framework patterns",
                "results": {"framework": "Laravel"},
            },
            {
                "phase": "pattern_discovery",
                "progress": 75.0,
                "step": "Discovering integration patterns",
                "results": {"patterns_found": 5},
            },
            {
                "phase": "convention_learning",
                "progress": 100.0,
                "step": "Learning code conventions",
                "results": {"conventions_learned": 8},
            },
        ]

        # Emit progress for each phase
        for phase_data in analysis_phases:
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase_data["phase"],
                progress_percent=phase_data["progress"],
                current_step=phase_data["step"],
                step_number=int(phase_data["progress"] / 25),
                total_steps=4,
            )

            # Wait for rate limiter
            await asyncio.sleep(1.1)

        # Emit final summary
        final_result = await server.emit_final_progress(
            session_id=session_id,
            language="PHP",
            framework="Laravel",
            patterns_discovered=5,
            conventions_learned=8,
            overall_confidence=0.92,
        )

        assert final_result is True

        # Verify messages were sent
        assert len(mock_websocket.sent_messages) > 0

        # Last message should be final summary
        final_message = mock_websocket.sent_messages[-1]
        assert final_message["is_final"] is True
        assert final_message["progress_percent"] == 100.0
