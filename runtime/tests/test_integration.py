"""
ProcessOS End-to-End Integration Tests

Sprint 4, Story S4-004: End-to-End Integration Tests
Comprehensive integration tests validating full stack:
engine + provider + validation + cost tracking + telemetry
"""

import os
import json
import pytest
from unittest.mock import MagicMock


# =============================================================================
# Task 1: Mock Integration Test Suite
# =============================================================================

class TestEngineIntegration:
    """Full stack integration tests with mock provider."""

    def test_single_step_playbook_executes_all_components(self, tmp_path):
        """AC1: Single step executes with all components integrated."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        # Create mock provider with valid response
        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Integration test"}',
            model="mock-integration",
            usage={"input_tokens": 100, "output_tokens": 50}
        )
        provider = MockAgentProvider(response=canned_response)

        # Create single-step playbook
        playbook_path = tmp_path / "single_step_playbook.yaml"
        playbook_path.write_text("""
playbook_id: integration-test-single
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: test-agent
    inputs_spec:
      input_data:
        type: string
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: integration-test
name: IntegrationTest
version: "1.0.0"
""")

        # Run playbook
        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Verify success
        assert success, f"Single step playbook should succeed: {error}"
        assert state.get("run_id"), "Should have run_id in state"

        # Verify step executed
        steps = state.get("steps", [])
        assert len(steps) == 1, "Should have 1 step"
        assert steps[0].get("status") == "completed", "Step should be completed"

    def test_multi_step_playbook_executes_with_gates(self, tmp_path):
        """AC1: Multi-step playbook executes with gates between steps."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        # Create provider that returns valid responses for multiple calls
        call_count = [0]
        responses = [
            AgentResponse(
                content='{"decision": "proceed", "reasoning": "Step 1 complete"}',
                model="mock",
                usage={"input_tokens": 100, "output_tokens": 50}
            ),
            AgentResponse(
                content='{"decision": "proceed", "reasoning": "Step 2 complete"}',
                model="mock",
                usage={"input_tokens": 120, "output_tokens": 60}
            ),
        ]

        class MultiResponseProvider(MockAgentProvider):
            def invoke(self, prompt: str, context: dict, timeout: float = 60.0) -> AgentResponse:
                if call_count[0] < len(responses):
                    response = responses[call_count[0]]
                    call_count[0] += 1
                    return response
                return super().invoke(prompt, context, timeout)

        provider = MultiResponseProvider()

        # Create multi-step playbook with gate
        playbook_path = tmp_path / "multi_step_playbook.yaml"
        playbook_path.write_text("""
playbook_id: integration-test-multi
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    sequence: 1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: step1_output

  - step_id: step_2
    agent_id: agent-2
    sequence: 2
    gates:
      - gate_type: artifact_exists
        parameters:
          artifact_kind: step1_output
    inputs_spec:
      prev_output:
        type: artifact
        artifact_kind: step1_output
    outputs_spec:
      artifact:
        artifact_kind: step2_output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: integration-test
name: IntegrationTest
version: "1.0.0"
""")

        # Run playbook
        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Verify success
        assert success, f"Multi-step playbook should succeed: {error}"

        # Verify both steps executed
        steps = state.get("steps", [])
        assert len(steps) == 2, f"Should have 2 steps, got {len(steps)}"
        for step in steps:
            assert step.get("status") == "completed", f"Step {step.get('step_id')} not completed"

    def test_telemetry_written_to_file(self, tmp_path):
        """AC1: Telemetry events captured correctly to file."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Telemetry test"}',
            model="mock-telemetry",
            usage={"input_tokens": 50, "output_tokens": 25}
        )
        provider = MockAgentProvider(response=canned_response)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: telemetry-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: telemetry-test
name: TelemetryTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Check telemetry file exists
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        assert telemetry_file.exists(), "Telemetry file should be created"

        # Parse and verify events
        events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
        assert len(events) > 0, "Should have telemetry events"

        # Should have run_started event
        event_types = [e.get("event_type") for e in events]
        assert "run_started" in event_types, "Should have run_started event"

        # Should have cost event (from successful invoke)
        assert "agent_cost" in event_types, "Should have agent_cost event"

    def test_cost_tracking_records_created(self, tmp_path):
        """AC1: Cost tracking records created for run."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse
        from cost_tracker import get_global_tracker

        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Cost test"}',
            model="mock-cost",
            usage={"input_tokens": 200, "output_tokens": 100}
        )
        provider = MockAgentProvider(response=canned_response)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: cost-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: cost-test
name: CostTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Verify cost tracking
        run_id = state.get("run_id")
        tracker = get_global_tracker()
        summary = tracker.get_run_total(run_id)

        assert summary["call_count"] >= 1, "Should have recorded at least one call"
        assert summary["total_input_tokens"] >= 200, "Should have input tokens"
        assert summary["total_output_tokens"] >= 100, "Should have output tokens"
        assert summary["estimated_cost_usd"] > 0, "Should have cost estimate"

    def test_artifacts_generated_and_registered(self, tmp_path):
        """AC1: Artifacts generated and registered in state."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Artifact test", "artifacts": [{"kind": "test", "content": "test content"}]}',
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50}
        )
        provider = MockAgentProvider(response=canned_response)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: artifact-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test_artifact
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: artifact-test
name: ArtifactTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Verify artifacts
        artifacts = state.get("artifacts", [])
        assert len(artifacts) >= 1, "Should have at least one artifact"
        assert any(a.get("artifact_kind") == "test_artifact" for a in artifacts), \
            "Should have test_artifact kind"


# =============================================================================
# Task 2: Real LLM Test Suite (Skipable)
# =============================================================================

@pytest.mark.real_llm
class TestRealLLMIntegration:
    """Tests requiring PROCESSOS_LLM_ENABLED=true."""

    @pytest.fixture(autouse=True)
    def skip_if_no_llm(self):
        """Skip all tests in this class if real LLM not enabled."""
        if os.environ.get("PROCESSOS_LLM_ENABLED", "").lower() != "true":
            pytest.skip("Requires PROCESSOS_LLM_ENABLED=true for real API test")

    def test_real_single_step_playbook(self, tmp_path):
        """AC2: Real API call works end-to-end with single step."""
        from engine import run_playbook
        from agent_provider import get_provider

        provider = get_provider(use_real_llm=True)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: real-llm-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: real-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
    prompt: |
      Return a simple JSON response:
      {"decision": "proceed", "reasoning": "Test successful"}
      ONLY return the JSON, no other text.
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: real-llm-test
name: RealLLMTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        assert success, f"Real LLM single step should succeed: {error}"
        assert state.get("run_id"), "Should have run_id"

    def test_real_multi_step_playbook(self, tmp_path):
        """AC2: Real API call works end-to-end with multi-step."""
        from engine import run_playbook
        from agent_provider import get_provider

        provider = get_provider(use_real_llm=True)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: real-llm-multi
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    sequence: 1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: step1_output
    prompt: |
      Return a simple JSON response:
      {"decision": "proceed", "reasoning": "Step 1 complete"}
      ONLY return the JSON, no other text.

  - step_id: step_2
    agent_id: agent-2
    sequence: 2
    gates:
      - gate_type: artifact_exists
        parameters:
          artifact_kind: step1_output
    inputs_spec:
      prev_output:
        type: artifact
        artifact_kind: step1_output
    outputs_spec:
      artifact:
        artifact_kind: step2_output
    prompt: |
      Return a simple JSON response:
      {"decision": "proceed", "reasoning": "Step 2 complete"}
      ONLY return the JSON, no other text.
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: real-llm-multi
name: RealLLMMulti
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        assert success, f"Real LLM multi-step should succeed: {error}"

        steps = state.get("steps", [])
        assert len(steps) == 2, f"Should have 2 steps, got {len(steps)}"

    def test_real_llm_cost_tracking_accuracy(self, tmp_path):
        """AC2: Cost tracking is accurate with real LLM."""
        from engine import run_playbook
        from agent_provider import get_provider
        from cost_tracker import get_global_tracker

        provider = get_provider(use_real_llm=True)

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: cost-accuracy-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
    prompt: |
      Return EXACTLY this JSON with no other text:
      {"decision": "proceed", "reasoning": "Cost tracking test"}
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: cost-accuracy
name: CostAccuracy
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        run_id = state.get("run_id")
        tracker = get_global_tracker()
        summary = tracker.get_run_total(run_id)

        # With real LLM, should have actual token counts
        assert summary["total_input_tokens"] > 0, "Should have real input tokens"
        assert summary["total_output_tokens"] > 0, "Should have real output tokens"
        assert summary["estimated_cost_usd"] > 0, "Should have positive cost"


# =============================================================================
# Task 3: Error Path Tests
# =============================================================================

class TestErrorHandling:
    """Error path coverage tests."""

    def test_timeout_handled_gracefully(self, tmp_path):
        """AC3: Timeout emits event and fails step gracefully."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentTimeoutError

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = AgentTimeoutError(
            "Agent call timed out after 30s",
            timeout=30.0,
            elapsed=30.5
        )

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: timeout-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: timeout-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: timeout-test
name: TimeoutTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Run should fail but not crash
        assert not success, "Run should fail on timeout"
        assert "timed out" in error.lower(), f"Error should mention timeout: {error}"

        # Should have emitted telemetry
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        if telemetry_file.exists():
            events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
            timeout_events = [e for e in events if e.get("event_type") == "agent_timeout"]
            assert len(timeout_events) >= 1, "Should have timeout telemetry event"
            assert timeout_events[0]["criticality"] == "high", "Timeout should be high criticality"

    def test_validation_failure_handled_gracefully(self, tmp_path):
        """AC3: Invalid output emits event and fails step gracefully."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse, AgentOutputValidationError

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"invalid": "output without decision field"}',
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50}
        )
        mock_provider.validate_output.side_effect = AgentOutputValidationError(
            "Missing required field: decision",
            step_id="step_1",
            agent_id="validation-agent"
        )

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: validation-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: validation-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: validation-test
name: ValidationTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Run should fail but not crash
        assert not success, "Run should fail on validation error"
        assert "validation" in error.lower() or "decision" in error.lower(), \
            f"Error should mention validation: {error}"

        # Should have emitted telemetry
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        if telemetry_file.exists():
            events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
            error_events = [e for e in events if "failed" in e.get("event_type", "").lower() or
                          "validation" in e.get("event_type", "").lower()]
            assert len(error_events) >= 1, "Should have validation failure telemetry event"

    def test_gate_failure_handled_gracefully(self, tmp_path):
        """AC3: Gate failure handled gracefully with appropriate telemetry."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        # Provider that returns valid response but for a step that has failed gate
        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Should not reach this"}',
            model="mock",
            usage={"input_tokens": 100, "output_tokens": 50}
        )
        provider = MockAgentProvider(response=canned_response)

        # Playbook where step 2 has gate requiring artifact from step 1,
        # but step 1 is missing (will cause gate to fail)
        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: gate-failure-test
playbook_version: "1.0"
steps:
  - step_id: step_2
    agent_id: agent-2
    sequence: 1
    gates:
      - gate_type: artifact_exists
        parameters:
          artifact_kind: missing_artifact
        on_failure: halt_with_reason
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: step2_output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: gate-test
name: GateTest
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Run should fail due to gate
        assert not success, "Run should fail on gate failure"
        assert "gate" in error.lower() or "artifact" in error.lower(), \
            f"Error should mention gate or artifact: {error}"

    def test_graceful_degradation_on_known_error(self, tmp_path):
        """AC3: Known provider errors (like timeout) handled without crashing."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentTimeoutError

        # Test with AgentTimeoutError - a known error type that engine handles
        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = AgentTimeoutError(
            "Provider timeout for graceful degradation test",
            timeout=60.0,
            elapsed=60.1
        )

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: error-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: error-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: error-test
name: ErrorTest
version: "1.0.0"
""")

        # Should not raise - should handle gracefully
        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Should fail gracefully (not crash)
        assert not success, "Run should fail on provider error"
        assert state is not None, "Should return state even on error"
        assert "timed out" in error.lower(), "Error should mention the timeout"

    def test_error_telemetry_emitted(self, tmp_path):
        """AC3: Error events are emitted to telemetry."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentTimeoutError

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = AgentTimeoutError(
            "Timeout for telemetry test",
            timeout=60.0,
            elapsed=60.5
        )

        playbook_path = tmp_path / "playbook.yaml"
        playbook_path.write_text("""
playbook_id: telemetry-error-test
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: telemetry-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: telemetry-error
name: TelemetryError
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Check telemetry file for error events
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        assert telemetry_file.exists(), "Telemetry file should be created even on error"

        events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]

        # Should have error-related events
        error_event_types = ["agent_timeout", "step_failed", "run_failed"]
        has_error_event = any(
            e.get("event_type") in error_event_types or
            "error" in e.get("event_type", "").lower() or
            "failed" in e.get("event_type", "").lower() or
            "timeout" in e.get("event_type", "").lower()
            for e in events
        )
        assert has_error_event, "Should have error-related telemetry event"
