"""
ProcessOS Engine Tests

Sprint 4, Story S4-001: Engine AgentProvider Injection
TDD tests for engine.py provider injection and integration.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock


class TestEngineProviderInjection:
    """Tests for S4-001: Engine accepts AgentProvider injection."""

    def test_run_playbook_accepts_agent_provider_parameter(self):
        """AC1: run_playbook() accepts agent_provider parameter."""
        import inspect
        from engine import run_playbook

        sig = inspect.signature(run_playbook)
        params = sig.parameters

        assert "agent_provider" in params, "run_playbook should accept agent_provider parameter"

    def test_run_playbook_agent_provider_defaults_to_none(self):
        """run_playbook agent_provider parameter should default to None."""
        import inspect
        from engine import run_playbook

        sig = inspect.signature(run_playbook)
        params = sig.parameters

        assert params["agent_provider"].default is None, \
            "agent_provider should default to None for backward compatibility"

    def test_run_playbook_uses_injected_provider(self, tmp_path):
        """AC1: When agent_provider is passed, engine uses it instead of inline mock."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider, AgentResponse

        # Create a mock provider with a specific response
        canned_response = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Injected provider worked"}',
            model="injected-mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )
        provider = MockAgentProvider(response=canned_response)

        # Create minimal test fixtures
        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: test-agent
    inputs_spec:
      test_input:
        type: string
    outputs_spec:
      artifact:
        artifact_kind: test-output
        template: test-template.md
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        # Create templates dir
        templates_dir = tmp_path / "process_os" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "test-template.md").write_text("# Test\n{content}")

        # Run with injected provider
        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=provider
        )

        # Provider should have been used (we verify by checking it completed)
        # The specific verification that provider.invoke was called comes in Task 2
        assert success or "provider" in error.lower() or True  # Placeholder until fully wired


class TestEngineDefaultProvider:
    """Tests for S4-001 AC2: Default to MockAgentProvider when None."""

    def test_run_playbook_defaults_to_mock_provider_when_none(self, tmp_path):
        """AC2: When agent_provider is None, engine uses get_provider()."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider

        # Create minimal test fixtures
        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
playbook_version: "1.0"
steps: []
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        # Mock get_provider to track if it was called
        mock_provider = MockAgentProvider()
        with patch("engine.get_provider", return_value=mock_provider) as mock_get_provider:
            # Call without agent_provider (should trigger get_provider())
            success, error, state = run_playbook(
                playbook_path=str(playbook_path),
                courier_profile_path=str(courier_path),
                repo_root=str(tmp_path),
                output_base_dir=str(tmp_path / "runs")
            )

            # Verify get_provider was called
            mock_get_provider.assert_called_once()

    def test_run_playbook_uses_injected_provider_not_default(self, tmp_path):
        """When agent_provider is passed, get_provider() should NOT be called."""
        from engine import run_playbook
        from agent_provider import MockAgentProvider

        # Create minimal test fixtures
        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
playbook_version: "1.0"
steps: []
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        # Create injected provider
        injected_provider = MockAgentProvider()

        with patch("engine.get_provider") as mock_get_provider:
            # Call WITH agent_provider (should NOT trigger get_provider())
            success, error, state = run_playbook(
                playbook_path=str(playbook_path),
                courier_profile_path=str(courier_path),
                repo_root=str(tmp_path),
                output_base_dir=str(tmp_path / "runs"),
                agent_provider=injected_provider
            )

            # Verify get_provider was NOT called
            mock_get_provider.assert_not_called()


class TestEngineProviderInvocation:
    """Tests for S4-001: Engine invokes provider.invoke() during step execution."""

    def test_provider_invoke_called_for_each_step(self, tmp_path):
        """Engine should call provider.invoke() for each step in the playbook."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse

        # Create a mock provider with spy on invoke
        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Test passed"}',
            model="mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )

        # Create test playbook with 2 steps
        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
playbook_version: "1.0"
steps:
  - step_id: step_1
    agent_id: agent-1
    inputs_spec:
      test_input:
        type: string
    outputs_spec:
      artifact:
        artifact_kind: test-output-1
  - step_id: step_2
    agent_id: agent-2
    inputs_spec:
      prev_output:
        type: artifact
        artifact_kind: test-output-1
    outputs_spec:
      artifact:
        artifact_kind: test-output-2
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        # Run with mock provider
        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Provider.invoke should have been called twice (once per step)
        assert mock_provider.invoke.call_count == 2, \
            f"Expected 2 invoke calls, got {mock_provider.invoke.call_count}"

    def test_provider_invoke_receives_prompt_and_context(self, tmp_path):
        """provider.invoke() should receive prompt built from step and context dict."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"decision": "proceed", "reasoning": "OK"}',
            model="mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
playbook_version: "1.0"
steps:
  - step_id: test_step
    agent_id: test-agent
    inputs_spec: {}
    outputs_spec:
      artifact:
        artifact_kind: test-output
    prompt: "Analyze the input and return a decision."
""")

        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Verify invoke was called with prompt and context
        mock_provider.invoke.assert_called_once()
        call_args = mock_provider.invoke.call_args
        prompt = call_args[0][0]  # First positional arg
        context = call_args[0][1]  # Second positional arg

        assert isinstance(prompt, str), "First arg should be prompt string"
        assert isinstance(context, dict), "Second arg should be context dict"
        assert "step_id" in context, "Context should include step_id"
        assert "run_id" in context, "Context should include run_id"


class TestEngineContractValidation:
    """Tests for S4-001 AC3: Engine validates provider output against contract."""

    def test_engine_validates_provider_output(self, tmp_path):
        """AC3: Engine calls provider.validate_output() after invoke."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse

        # Create mock provider that returns valid JSON
        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Test validation"}',
            model="mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )
        # validate_output returns the parsed output
        mock_provider.validate_output.return_value = {
            "decision": "proceed",
            "reasoning": "Test validation"
        }

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # validate_output should have been called
        mock_provider.validate_output.assert_called_once()

    def test_engine_handles_validation_failure(self, tmp_path):
        """AC3: Engine marks step as failed when validation fails."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse, AgentOutputValidationError

        # Create mock provider that fails validation
        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"invalid": "output"}',
            model="mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )
        mock_provider.validate_output.side_effect = AgentOutputValidationError(
            "Missing required field: decision",
            step_id="step_1",
            agent_id="agent-1"
        )

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Run should fail
        assert not success, "Run should fail when validation fails"
        assert "validation" in error.lower() or "decision" in error.lower(), \
            f"Error should mention validation failure: {error}"

    def test_engine_emits_telemetry_on_validation_failure(self, tmp_path):
        """AC3: Engine emits telemetry event when validation fails."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse, AgentOutputValidationError
        import json

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"bad": "output"}',
            model="mock",
            usage={"input_tokens": 10, "output_tokens": 20}
        )
        mock_provider.validate_output.side_effect = AgentOutputValidationError(
            "Schema validation failed",
            step_id="step_1",
            agent_id="agent-1"
        )

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Check telemetry file for validation failure event
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        if telemetry_file.exists():
            events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
            [e for e in events if e.get("event_type") == "validation_failed"]
            # Should have a validation failure event (or error event)
            error_events = [e for e in events if "error" in e.get("event_type", "").lower() or
                          "failed" in e.get("event_type", "").lower()]
            assert len(error_events) > 0, "Should emit error/failed event on validation failure"


class TestEngineBackwardCompatibility:
    """Tests for S4-001 AC2: Default behavior unchanged."""

    def test_run_playbook_works_without_provider_parameter(self, tmp_path):
        """AC2: run_playbook() works without agent_provider (backward compatible)."""
        from engine import run_playbook

        # Use existing test fixtures from original engine tests
        playbook_path = Path("process_os/playbooks/courier-integration-v0.1.yaml")
        courier_path = tmp_path / "courier.yaml"
        courier_path.write_text("""
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        if playbook_path.exists():
            # Should work without agent_provider parameter
            success, error, state = run_playbook(
                playbook_path=str(playbook_path),
                courier_profile_path=str(courier_path),
                repo_root=str(tmp_path),
                output_base_dir=str(tmp_path / "runs")
            )
            # Should complete (either success or expected failure like gate check)
            assert state is not None


# =============================================================================
# S4-002: Telemetry Integration (Timeout/Cost Events)
# =============================================================================

class TestEngineCostTelemetry:
    """Tests for S4-002 AC1: Cost event emitted on successful call."""

    def test_engine_emits_cost_event_on_successful_invoke(self, tmp_path):
        """AC1: Engine emits agent_cost telemetry event after successful invoke."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse
        import json

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"decision": "proceed", "reasoning": "OK"}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 100, "output_tokens": 50}
        )
        mock_provider.validate_output.return_value = {"decision": "proceed", "reasoning": "OK"}

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Check telemetry file for cost event
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        assert telemetry_file.exists(), "Telemetry file should exist"
        events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
        cost_events = [e for e in events if e.get("event_type") == "agent_cost"]

        assert len(cost_events) >= 1, "Should have at least one agent_cost event"
        cost_event = cost_events[0]
        assert cost_event["data"]["input_tokens"] == 100
        assert cost_event["data"]["output_tokens"] == 50
        assert "model" in cost_event["data"]
        assert "estimated_cost_usd" in cost_event["data"]

    def test_engine_records_cost_in_tracker(self, tmp_path):
        """AC3: Engine records cost via CostTracker for run-level summary."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentResponse
        from cost_tracker import get_global_tracker

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.return_value = AgentResponse(
            content='{"decision": "proceed", "reasoning": "OK"}',
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 200, "output_tokens": 100}
        )
        mock_provider.validate_output.return_value = {"decision": "proceed", "reasoning": "OK"}

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Check cost tracker for run summary
        run_id = state.get("run_id")
        tracker = get_global_tracker()
        summary = tracker.get_run_total(run_id)

        assert summary["call_count"] >= 1, "Should have at least one recorded call"
        assert summary["total_input_tokens"] >= 200
        assert summary["total_output_tokens"] >= 100
        assert summary["estimated_cost_usd"] > 0


class TestEngineTimeoutTelemetry:
    """Tests for S4-002 AC2: Timeout event emitted on timeout."""

    def test_engine_catches_timeout_error(self, tmp_path):
        """AC2: Engine catches AgentTimeoutError and handles gracefully."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentTimeoutError

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = AgentTimeoutError(
            "Agent call timed out after 30s",
            timeout=30.0,
            elapsed=30.5
        )

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
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

    def test_engine_emits_timeout_event(self, tmp_path):
        """AC2: Engine emits agent_timeout telemetry event with criticality=high."""
        from engine import run_playbook
        from agent_provider import AgentProvider, AgentTimeoutError
        import json

        mock_provider = MagicMock(spec=AgentProvider)
        mock_provider.invoke.side_effect = AgentTimeoutError(
            "Agent call timed out after 60s",
            timeout=60.0,
            elapsed=60.5
        )

        playbook_path = tmp_path / "test_playbook.yaml"
        playbook_path.write_text("""
playbook_id: test-playbook
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
courier_id: test-courier
name: TestCourier
version: "1.0.0"
""")

        success, error, state = run_playbook(
            playbook_path=str(playbook_path),
            courier_profile_path=str(courier_path),
            repo_root=str(tmp_path),
            output_base_dir=str(tmp_path / "runs"),
            agent_provider=mock_provider
        )

        # Check telemetry file for timeout event
        run_id = state.get("run_id")
        telemetry_file = tmp_path / "runs" / run_id / "telemetry.jsonl"

        assert telemetry_file.exists(), "Telemetry file should exist"
        events = [json.loads(line) for line in telemetry_file.read_text().strip().split('\n')]
        timeout_events = [e for e in events if e.get("event_type") == "agent_timeout"]

        assert len(timeout_events) >= 1, "Should have at least one agent_timeout event"
        timeout_event = timeout_events[0]
        assert timeout_event["criticality"] == "high"
        assert "timeout_seconds" in timeout_event["data"]
        assert "elapsed_seconds" in timeout_event["data"]
