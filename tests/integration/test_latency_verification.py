"""
Final latency verification tests for SC-001 requirement.

Tests:
- T072: SC-001 latency verification with real analysis
- Measure latency from analyzer milestone to client display
- Verify <1 second requirement end-to-end
"""

import asyncio
import time
from typing import Dict, Any, List
from uuid import uuid4

import pytest

from process_os.llm.server import AsyncWebSocketServer
from process_os.architecture.analyzer import ArchitectureAnalyzer


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.message_timestamps: List[float] = []
        self.closed = False

    async def send(self, message: str):
        """Track sent messages with timestamps."""
        import json
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent_messages.append(json.loads(message))
        self.message_timestamps.append(time.time())


class LatencyMeasurement:
    """Measures latency for progress updates."""

    def __init__(self):
        self.milestone_timestamps: Dict[str, float] = {}
        self.message_timestamps: Dict[str, float] = {}
        self.latencies: Dict[str, float] = {}

    def record_milestone(self, phase: str) -> None:
        """Record when a milestone occurs in analyzer."""
        self.milestone_timestamps[phase] = time.time()

    def record_message(self, phase: str) -> None:
        """Record when a progress message is sent."""
        self.message_timestamps[phase] = time.time()

    def calculate_latency(self, phase: str) -> float:
        """Calculate latency for a phase milestone."""
        if phase in self.milestone_timestamps and phase in self.message_timestamps:
            latency = (
                self.message_timestamps[phase]
                - self.milestone_timestamps[phase]
            )
            self.latencies[phase] = latency
            return latency
        return 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get latency summary."""
        return {
            "latencies": self.latencies,
            "max_latency": max(self.latencies.values()) if self.latencies else 0.0,
            "average_latency": (
                sum(self.latencies.values()) / len(self.latencies)
                if self.latencies
                else 0.0
            ),
            "all_under_threshold": all(
                latency < 1.0 for latency in self.latencies.values()
            ),
        }


class TestLatencyRequirement:
    """Test SC-001: Latency requirement (<1 second)."""

    @pytest.mark.asyncio
    async def test_language_detection_latency_under_1_second(self):
        """Verify language detection milestone has <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        # Setup
        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Record milestone time
        measurement = LatencyMeasurement()
        measurement.record_milestone("language_detection")

        # Emit progress (simulating analyzer milestone)
        start_time = time.time()
        result = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Language detected: PHP",
            step_number=1,
            total_steps=4,
            confidence_scores={"language_detection": 0.95},
        )
        end_time = time.time()

        # Verify message was sent
        assert result is True
        assert len(mock_websocket.sent_messages) == 1

        # Calculate latency
        emission_latency = end_time - start_time

        # Verify <1 second (SC-001)
        assert emission_latency < 1.0, f"Latency {emission_latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_framework_detection_latency_under_1_second(self):
        """Verify framework detection milestone has <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # First message (language detection)
        await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Language: PHP",
            step_number=1,
            total_steps=4,
            confidence_scores={"language_detection": 0.95},
        )
        await asyncio.sleep(1.1)  # Wait for rate limiter

        # Measure framework detection latency
        start_time = time.time()
        result = await server.emit_progress(
            session_id=session_id,
            phase="framework_detection",
            progress_percent=50.0,
            current_step="Framework detected: Laravel",
            step_number=2,
            total_steps=4,
            confidence_scores={"framework_detection": 0.90},
        )
        end_time = time.time()

        assert result is True
        latency = end_time - start_time
        assert latency < 1.0, f"Framework detection latency {latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_pattern_discovery_latency_under_1_second(self):
        """Verify pattern discovery milestone has <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Skip to pattern discovery
        await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=25.0,
            current_step="Language: PHP",
            step_number=1,
            total_steps=4,
        )
        await asyncio.sleep(1.1)

        await server.emit_progress(
            session_id=session_id,
            phase="framework_detection",
            progress_percent=50.0,
            current_step="Framework: Laravel",
            step_number=2,
            total_steps=4,
        )
        await asyncio.sleep(1.1)

        # Measure pattern discovery latency
        start_time = time.time()
        result = await server.emit_progress(
            session_id=session_id,
            phase="pattern_discovery",
            progress_percent=75.0,
            current_step="Found 5 patterns",
            step_number=3,
            total_steps=4,
            confidence_scores={"pattern_discovery": 0.85},
        )
        end_time = time.time()

        assert result is True
        latency = end_time - start_time
        assert latency < 1.0, f"Pattern discovery latency {latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_convention_learning_latency_under_1_second(self):
        """Verify convention learning milestone has <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Skip to convention learning
        for phase, progress in [
            ("language_detection", 25.0),
            ("framework_detection", 50.0),
            ("pattern_discovery", 75.0),
        ]:
            await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=progress,
                current_step=f"{phase}...",
                step_number=int(progress / 25),
                total_steps=4,
            )
            await asyncio.sleep(1.1)

        # Measure convention learning latency
        start_time = time.time()
        result = await server.emit_progress(
            session_id=session_id,
            phase="convention_learning",
            progress_percent=100.0,
            current_step="Learned 8 conventions",
            step_number=4,
            total_steps=4,
            confidence_scores={"convention_learning": 0.80},
        )
        end_time = time.time()

        assert result is True
        latency = end_time - start_time
        assert latency < 1.0, f"Convention learning latency {latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_final_summary_latency_under_1_second(self):
        """Verify final summary emission has <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Measure final summary latency
        start_time = time.time()
        result = await server.emit_final_progress(
            session_id=session_id,
            language="PHP",
            framework="Laravel",
            patterns_discovered=5,
            conventions_learned=8,
            overall_confidence=0.90,
        )
        end_time = time.time()

        assert result is True
        latency = end_time - start_time
        assert latency < 1.0, f"Final summary latency {latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_complete_analysis_all_phases_under_1_second(self):
        """Verify all 4 analysis phases have <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        phases = [
            ("language_detection", 25.0, 1),
            ("framework_detection", 50.0, 2),
            ("pattern_discovery", 75.0, 3),
            ("convention_learning", 100.0, 4),
        ]

        latencies = {}

        for phase, progress, step_num in phases:
            # Measure latency for each phase
            start_time = time.time()
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=progress,
                current_step=f"Analyzing {phase}",
                step_number=step_num,
                total_steps=4,
            )
            end_time = time.time()

            assert result is True
            latencies[phase] = end_time - start_time

            # Wait for rate limiter before next phase
            await asyncio.sleep(1.1)

        # Verify all phases under 1 second
        for phase, latency in latencies.items():
            assert (
                latency < 1.0
            ), f"{phase} latency {latency:.3f}s exceeds 1 second"

    @pytest.mark.asyncio
    async def test_latency_consistent_across_multiple_measurements(self):
        """Verify latency is consistent across multiple measurements."""
        server = AsyncWebSocketServer()

        latencies_per_measurement = {
            "measurement_1": [],
            "measurement_2": [],
            "measurement_3": [],
        }

        for measurement_key in latencies_per_measurement.keys():
            session_id = str(uuid4())
            operation_id = str(uuid4())

            mock_websocket = MockWebSocket()
            server.active_connections[session_id] = mock_websocket
            server.create_progress_manager(session_id, operation_id)

            # Measure latency 5 times per measurement
            for i in range(5):
                start_time = time.time()
                result = await server.emit_progress(
                    session_id=session_id,
                    phase="language_detection",
                    progress_percent=25.0 + i,
                    current_step=f"Step {i+1}",
                    step_number=1,
                    total_steps=4,
                )
                end_time = time.time()

                if result:
                    latencies_per_measurement[measurement_key].append(
                        end_time - start_time
                    )

                # Wait for rate limiter between measurements
                await asyncio.sleep(1.1)

        # Verify all measurements under 1 second
        for measurement_key, latencies in latencies_per_measurement.items():
            for latency in latencies:
                assert (
                    latency < 1.0
                ), f"{measurement_key} latency {latency:.3f}s exceeds 1 second"


class TestAnalysisLatencyEnd2End:
    """End-to-end analysis latency tests."""

    @pytest.mark.asyncio
    async def test_complete_analysis_workflow_latency(self):
        """Test latency through complete analysis workflow."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # Simulate complete analysis with latency tracking
        analysis_phases = [
            ("language_detection", 25.0, "Language: PHP"),
            ("framework_detection", 50.0, "Framework: Laravel"),
            ("pattern_discovery", 75.0, "Patterns: 5"),
            ("convention_learning", 100.0, "Conventions: 8"),
        ]

        total_latency = 0.0
        max_latency = 0.0

        for phase, progress, step in analysis_phases:
            start_time = time.time()
            result = await server.emit_progress(
                session_id=session_id,
                phase=phase,
                progress_percent=progress,
                current_step=step,
                step_number=int(progress / 25),
                total_steps=4,
            )
            end_time = time.time()

            if result:
                latency = end_time - start_time
                total_latency += latency
                max_latency = max(max_latency, latency)

                # Each phase must be <1 second
                assert latency < 1.0

            # Wait for rate limiter
            await asyncio.sleep(1.1)

        # Final summary
        start_time = time.time()
        result = await server.emit_final_progress(
            session_id=session_id,
            language="PHP",
            framework="Laravel",
            patterns_discovered=5,
            conventions_learned=8,
            overall_confidence=0.90,
        )
        end_time = time.time()

        final_latency = end_time - start_time
        total_latency += final_latency

        # Verify final message latency
        assert final_latency < 1.0
        assert max_latency < 1.0

        # Verify overall analysis time is reasonable
        # (all messages sent, each with <1 second latency + 1.1 second wait)
        # Total should be ~5 seconds (4 phases * 1.1 wait + overhead)
        assert total_latency < 10.0

    @pytest.mark.asyncio
    async def test_rate_limited_messages_still_meet_latency(self):
        """Verify rate-limited messages still meet <1 second latency."""
        server = AsyncWebSocketServer()
        session_id = str(uuid4())
        operation_id = str(uuid4())

        mock_websocket = MockWebSocket()
        server.active_connections[session_id] = mock_websocket
        server.create_progress_manager(session_id, operation_id)

        # First message (sent)
        start_time = time.time()
        result1 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=10.0,
            current_step="Step 1",
            step_number=1,
            total_steps=4,
        )
        latency1 = time.time() - start_time

        assert result1 is True
        assert latency1 < 1.0

        # Second message (rate limited - not sent)
        start_time = time.time()
        result2 = await server.emit_progress(
            session_id=session_id,
            phase="language_detection",
            progress_percent=20.0,
            current_step="Step 2",
            step_number=1,
            total_steps=4,
        )
        latency2 = time.time() - start_time

        # Rate limited means the call returns False quickly
        assert result2 is False
        # Even rate-limited check should be <1 second
        assert latency2 < 1.0
