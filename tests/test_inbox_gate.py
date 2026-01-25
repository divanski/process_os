"""
ProcessOS Inbox Gate Tests

Tests for Sprint 8 Hotfix + Sprint 9 updates:
- Inbox gate checks for required materials
- Run BLOCKS (not halts) when materials missing (Sprint 9)
- Telemetry emits run_blocked (not run_succeeded) with criticality=critical
- Resume works when materials provided
- Distinct statuses: blocked (resumable), halted (system), failed (error)
"""

import json
import tempfile
from pathlib import Path

import pytest

from process_os.runtime.inbox_gate import (
    InboxGate,
    InboxGateConfig,
    InboxGateResult,
    check_inbox_materials,
)
from process_os.runtime.telemetry import TelemetrySink, load_events


class TestInboxGateConfig:
    """InboxGateConfig tests."""

    def test_default_required_one_of(self):
        """Default required_one_of includes common API doc formats."""
        config = InboxGateConfig(integration_id="fedex")

        assert "*.postman_collection.json" in config.required_one_of
        assert "openapi.yaml" in config.required_one_of
        assert "openapi.json" in config.required_one_of
        assert "swagger.yaml" in config.required_one_of

    def test_default_require_secrets_file(self):
        """Default requires secrets file."""
        config = InboxGateConfig(integration_id="fedex")
        assert config.require_secrets_file is True


class TestInboxGateMissingMaterials:
    """Tests for missing materials detection."""

    def test_fails_when_no_inbox_dir(self):
        """Gate fails when inbox directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            processos_dir.mkdir()

            config = InboxGateConfig(integration_id="fedex")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is False
            assert len(result.missing_items) > 0

    def test_fails_when_no_api_docs(self):
        """Gate fails when no API docs present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "fedex"
            inbox_dir.mkdir(parents=True)

            # Create empty inbox (no docs)
            (inbox_dir / "README.md").write_text("Empty")

            config = InboxGateConfig(integration_id="fedex")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is False
            assert any("API docs" in item for item in result.missing_items)

    def test_fails_when_no_secrets_file(self):
        """Gate fails when secrets file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "fedex"
            inbox_dir.mkdir(parents=True)

            # Provide API docs but no secrets
            (inbox_dir / "openapi.yaml").write_text("openapi: 3.0.0")

            config = InboxGateConfig(integration_id="fedex")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is False
            assert any("Credentials" in item or "secrets" in item.lower() for item in result.missing_items)

    def test_resume_instructions_included(self):
        """Missing materials result includes resume instructions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            processos_dir.mkdir()

            config = InboxGateConfig(integration_id="fedex")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is False
            assert "resume" in result.resume_instructions.lower()
            assert "fedex" in result.resume_instructions.lower()


class TestInboxGateMaterialsPresent:
    """Tests for when materials are present."""

    def test_passes_with_postman_collection(self):
        """Gate passes with Postman collection file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "fedex"
            secrets_dir = processos_dir / "secrets"
            inbox_dir.mkdir(parents=True)
            secrets_dir.mkdir()

            # Provide Postman collection
            (inbox_dir / "fedex.postman_collection.json").write_text('{"info": {}}')
            # Provide secrets file
            (secrets_dir / "integration_fedex.env").write_text("FEDEX_CLIENT_ID=xxx")

            config = InboxGateConfig(integration_id="fedex")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is True
            assert len(result.found_items) > 0

    def test_passes_with_openapi_yaml(self):
        """Gate passes with OpenAPI spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "dhl"
            secrets_dir = processos_dir / "secrets"
            inbox_dir.mkdir(parents=True)
            secrets_dir.mkdir()

            # Provide OpenAPI spec
            (inbox_dir / "openapi.yaml").write_text("openapi: 3.0.0")
            # Provide secrets file
            (secrets_dir / "integration_dhl.env").write_text("DHL_API_KEY=xxx")

            config = InboxGateConfig(integration_id="dhl")
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is True

    def test_passes_without_secrets_when_not_required(self):
        """Gate passes without secrets if require_secrets_file=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "fedex"
            inbox_dir.mkdir(parents=True)

            # Provide API docs only
            (inbox_dir / "openapi.json").write_text('{"openapi": "3.0.0"}')

            config = InboxGateConfig(integration_id="fedex", require_secrets_file=False)
            gate = InboxGate(processos_dir, config)
            result = gate.check()

            assert result.passed is True


class TestInboxGateConvenienceFunction:
    """Tests for check_inbox_materials helper."""

    def test_convenience_function_returns_tuple(self):
        """check_inbox_materials returns (passed, result) tuple."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            processos_dir.mkdir()

            passed, result = check_inbox_materials(processos_dir, "fedex")

            assert isinstance(passed, bool)
            assert isinstance(result, InboxGateResult)

    def test_convenience_function_passes_when_materials_present(self):
        """check_inbox_materials passes with valid materials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            processos_dir = Path(tmpdir) / ".processos"
            inbox_dir = processos_dir / "inbox" / "integrations" / "ups"
            secrets_dir = processos_dir / "secrets"
            inbox_dir.mkdir(parents=True)
            secrets_dir.mkdir()

            (inbox_dir / "swagger.yaml").write_text("swagger: 2.0")
            (secrets_dir / "integration_ups.env").write_text("UPS_KEY=xxx")

            passed, result = check_inbox_materials(processos_dir, "ups")

            assert passed is True


class TestTelemetryCriticality:
    """Tests for telemetry criticality levels."""

    def test_run_halted_is_critical(self):
        """run_halted event has criticality=critical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.emit("run_halted", "run-123", data={"reason": "awaiting_materials"})

            events = load_events(telemetry_path)
            assert len(events) == 1
            assert events[0]["criticality"] == "critical"

    def test_gate_halted_is_critical(self):
        """gate_halted event has criticality=critical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.emit("gate_halted", "run-123", data={"gate_id": "inbox_check"})

            events = load_events(telemetry_path)
            assert len(events) == 1
            assert events[0]["criticality"] == "critical"

    def test_run_succeeded_is_normal(self):
        """run_succeeded event has criticality=normal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.run_succeeded("run-123", steps_completed=3, artifacts_count=2)

            events = load_events(telemetry_path)
            # Sprint 9.1: run_succeeded emits both run_succeeded + run_completed
            assert len(events) == 2
            succeeded_events = [e for e in events if e["event_type"] == "run_succeeded"]
            assert len(succeeded_events) == 1
            assert succeeded_events[0]["criticality"] == "normal"


class TestTelemetryHaltAndBlockEvents:
    """Tests for halt and block telemetry events."""

    def test_run_halted_convenience_method(self):
        """run_halted convenience method includes reason and halt_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.run_halted(
                "run-123",
                reason="Invariant violation: drift detected",
                halt_type="drift",
            )

            events = load_events(telemetry_path)
            assert len(events) == 1

            event = events[0]
            assert event["event_type"] == "run_halted"
            assert event["criticality"] == "critical"
            assert event["data"]["reason"] == "Invariant violation: drift detected"
            assert event["data"]["halt_type"] == "drift"

    def test_run_blocked_convenience_method(self):
        """run_blocked convenience method includes missing_inputs and resume_command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.run_blocked(
                "run-123",
                reason="awaiting_inbox_materials",
                blocked_at_step="intake",
                blocked_at_gate="inbox_materials_check",
                missing_inputs=["openapi.yaml", "credentials"],
                workspace_id="ws-abc123",
            )

            events = load_events(telemetry_path)
            assert len(events) == 1

            event = events[0]
            assert event["event_type"] == "run_blocked"
            assert event["criticality"] == "critical"
            assert event["data"]["reason"] == "awaiting_inbox_materials"
            assert event["data"]["blocked_at_gate"] == "inbox_materials_check"
            assert "openapi.yaml" in event["data"]["missing_inputs"]
            assert "processos resume" in event["data"]["resume_command"]

    def test_gate_halted_convenience_method(self):
        """gate_halted convenience method includes gate details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_path = Path(tmpdir) / "telemetry.jsonl"
            sink = TelemetrySink(telemetry_path)

            sink.gate_halted(
                "run-123",
                step_id="step-0",
                gate_id="inbox_materials_check",
                reason="Missing API documentation",
                missing_items=["postman_collection.json"],
            )

            events = load_events(telemetry_path)
            assert len(events) == 1

            event = events[0]
            assert event["event_type"] == "gate_halted"
            assert event["criticality"] == "critical"
            assert event["data"]["gate_id"] == "inbox_materials_check"


class TestRunStateBlockedFields:
    """Tests for RunState blocked-related fields (Sprint 9)."""

    def test_run_state_has_blocked_reason(self):
        """RunState includes blocked_reason field."""
        from process_os.runtime.workspace_runner import RunState

        state = RunState(
            run_id="run-123",
            workspace_id="ws-abc",
            command_id="cmd-xyz",
            playbook_id="playbook-test",
            status="blocked",
            blocked_reason="Awaiting courier materials",
            blocked_gate="inbox_materials_check",
            blocked_inputs=["openapi.yaml", "credentials"],
        )

        assert state.blocked_reason == "Awaiting courier materials"
        assert state.blocked_gate == "inbox_materials_check"
        assert len(state.blocked_inputs) == 2

    def test_run_state_blocked_fields_in_to_dict(self):
        """RunState.to_dict includes blocked fields."""
        from process_os.runtime.workspace_runner import RunState

        state = RunState(
            run_id="run-123",
            workspace_id="ws-abc",
            command_id="cmd-xyz",
            playbook_id="playbook-test",
            status="blocked",
            blocked_reason="Awaiting materials",
            blocked_gate="gate-1",
            blocked_at="2026-01-20T12:00:00Z",
            blocked_inputs=["api_docs", "credentials"],
        )

        d = state.to_dict()

        assert d["blocked_reason"] == "Awaiting materials"
        assert d["blocked_gate"] == "gate-1"
        assert d["blocked_at"] == "2026-01-20T12:00:00Z"
        assert "api_docs" in d["blocked_inputs"]

    def test_run_state_blocked_vs_halted_vs_failed_distinct(self):
        """blocked, halted, and failed statuses are distinct."""
        from process_os.runtime.workspace_runner import RunState

        # Blocked state (awaiting user input - resumable)
        blocked = RunState(
            run_id="run-1",
            workspace_id="ws-1",
            command_id="cmd-1",
            playbook_id="pb-1",
            status="blocked",
            blocked_reason="Awaiting API docs",
            blocked_gate="inbox_check",
            blocked_inputs=["openapi.yaml"],
        )

        # Halted state (system halt - not resumable)
        halted = RunState(
            run_id="run-2",
            workspace_id="ws-1",
            command_id="cmd-1",
            playbook_id="pb-1",
            status="halted",
            halt_reason="Drift detected",
        )

        # Failed state (error during execution)
        failed = RunState(
            run_id="run-3",
            workspace_id="ws-1",
            command_id="cmd-1",
            playbook_id="pb-1",
            status="failed",
            failure_reason="Agent timeout",
            failed_step="step-2",
        )

        # Blocked is for user input
        assert blocked.blocked_reason is not None
        assert blocked.blocked_gate is not None
        assert blocked.halt_reason is None
        assert blocked.failure_reason is None

        # Halted is for system issues
        assert halted.halt_reason is not None
        assert halted.blocked_reason is None
        assert halted.failure_reason is None

        # Failed is for execution errors
        assert failed.failure_reason is not None
        assert failed.blocked_reason is None
        assert failed.halt_reason is None

        assert failed.failure_reason is not None
        assert failed.halt_reason is None
