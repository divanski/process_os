"""
ProcessOS Gate Halt Tests

Tests for SN-006 and SN-011:
- Failed gate halts run with deterministic reason
- Gate results are deterministic
- Different gate types work correctly
"""

import pytest
import sys
import tempfile
from pathlib import Path

# Add process_os to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from process_os.runtime.gate_enforcer import GateEnforcer, GateResult
from process_os.runtime.artifact_registry import ArtifactRegistry


class TestGateEnforcerBasics:
    """Basic gate enforcer tests."""

    def test_artifact_exists_gate_passes(self):
        """artifact_exists gate passes when artifact present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            registry.register("test content", "test_kind", "step-0")

            enforcer = GateEnforcer(registry)

            result = enforcer.evaluate(
                gate_id="gate-1",
                gate_type="artifact_exists",
                parameters={"artifact_kind": "test_kind"},
                state={"artifacts": []}
            )

            assert result.passed
            assert "exists" in result.reason.lower()

    def test_artifact_exists_gate_fails(self):
        """artifact_exists gate fails when artifact missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            # No artifacts registered

            enforcer = GateEnforcer(registry)

            result = enforcer.evaluate(
                gate_id="gate-1",
                gate_type="artifact_exists",
                parameters={"artifact_kind": "missing_kind"},
                state={"artifacts": []}
            )

            assert not result.passed
            assert "not found" in result.reason.lower()

    def test_gate_failure_reason_is_deterministic(self):
        """Same gate failure produces same reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            enforcer = GateEnforcer(registry)

            result1 = enforcer.evaluate(
                gate_id="gate-1",
                gate_type="artifact_exists",
                parameters={"artifact_kind": "missing"},
                state={}
            )

            enforcer.clear_results()

            result2 = enforcer.evaluate(
                gate_id="gate-1",
                gate_type="artifact_exists",
                parameters={"artifact_kind": "missing"},
                state={}
            )

            assert result1.reason == result2.reason


class TestGateHaltBehavior:
    """Gate halt behavior tests."""

    def test_check_all_stops_on_first_failure(self):
        """check_all stops evaluating after first failure."""
        enforcer = GateEnforcer()

        gates = [
            {"gate_id": "gate-1", "gate_type": "artifact_exists", "parameters": {"artifact_kind": "missing1"}},
            {"gate_id": "gate-2", "gate_type": "artifact_exists", "parameters": {"artifact_kind": "missing2"}},
            {"gate_id": "gate-3", "gate_type": "artifact_exists", "parameters": {"artifact_kind": "missing3"}},
        ]

        all_passed, results = enforcer.check_all(gates, {})

        assert not all_passed
        # Should only have one result (stopped at first failure)
        assert len(results) == 1
        assert results[0].gate_id == "gate-1"

    def test_check_all_returns_all_passed_when_success(self):
        """check_all returns all results when all pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            registry.register("content1", "kind1", "step-0")
            registry.register("content2", "kind2", "step-0")

            enforcer = GateEnforcer(registry)

            gates = [
                {"gate_id": "gate-1", "gate_type": "artifact_exists", "parameters": {"artifact_kind": "kind1"}},
                {"gate_id": "gate-2", "gate_type": "artifact_exists", "parameters": {"artifact_kind": "kind2"}},
            ]

            all_passed, results = enforcer.check_all(gates, {})

            assert all_passed
            assert len(results) == 2
            assert all(r.passed for r in results)


class TestAllArtifactsPresentGate:
    """all_artifacts_present gate tests."""

    def test_all_artifacts_present_passes(self):
        """all_artifacts_present passes when all artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            registry.register("a", "kind_a", "step-0")
            registry.register("b", "kind_b", "step-0")
            registry.register("c", "kind_c", "step-0")

            enforcer = GateEnforcer(registry)

            result = enforcer.evaluate(
                gate_id="gate-all",
                gate_type="all_artifacts_present",
                parameters={"required_artifacts": ["kind_a", "kind_b", "kind_c"]},
                state={}
            )

            assert result.passed

    def test_all_artifacts_present_fails_with_missing(self):
        """all_artifacts_present fails when some artifacts missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ArtifactRegistry(Path(tmpdir) / "artifacts")
            registry.register("a", "kind_a", "step-0")
            # kind_b and kind_c not registered

            enforcer = GateEnforcer(registry)

            result = enforcer.evaluate(
                gate_id="gate-all",
                gate_type="all_artifacts_present",
                parameters={"required_artifacts": ["kind_a", "kind_b", "kind_c"]},
                state={}
            )

            assert not result.passed
            assert "missing" in result.reason.lower()
            assert "kind_b" in result.details["missing"]
            assert "kind_c" in result.details["missing"]


class TestFieldValueGate:
    """field_value gate tests."""

    def test_field_value_passes(self):
        """field_value passes when field matches expected."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-field",
            gate_type="field_value",
            parameters={"field": "status", "expected": "approved"},
            state={"status": "approved"}
        )

        assert result.passed

    def test_field_value_fails_mismatch(self):
        """field_value fails when field doesn't match."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-field",
            gate_type="field_value",
            parameters={"field": "status", "expected": "approved"},
            state={"status": "rejected"}
        )

        assert not result.passed
        assert "unexpected" in result.reason.lower()

    def test_field_value_fails_missing(self):
        """field_value fails when field missing."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-field",
            gate_type="field_value",
            parameters={"field": "missing_field", "expected": "value"},
            state={}
        )

        assert not result.passed
        assert "not found" in result.reason.lower()

    def test_nested_field_value(self):
        """field_value works with nested fields."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-nested",
            gate_type="field_value",
            parameters={"field": "result.status", "expected": "success"},
            state={"result": {"status": "success"}}
        )

        assert result.passed


class TestStepCompletedGate:
    """step_completed gate tests."""

    def test_step_completed_passes(self):
        """step_completed passes when step is completed."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-step",
            gate_type="step_completed",
            parameters={"step_id": "step-1"},
            state={"steps": [{"step_id": "step-1", "status": "completed"}]}
        )

        assert result.passed

    def test_step_completed_fails_not_completed(self):
        """step_completed fails when step not completed."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-step",
            gate_type="step_completed",
            parameters={"step_id": "step-1"},
            state={"steps": [{"step_id": "step-1", "status": "running"}]}
        )

        assert not result.passed
        assert "not completed" in result.reason.lower()

    def test_step_completed_fails_not_found(self):
        """step_completed fails when step not found."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-step",
            gate_type="step_completed",
            parameters={"step_id": "step-missing"},
            state={"steps": []}
        )

        assert not result.passed
        assert "not found" in result.reason.lower()


class TestCustomGates:
    """Custom gate registration tests."""

    def test_custom_gate_registration(self):
        """Can register and use custom gates."""
        enforcer = GateEnforcer()

        def custom_validator(params, state):
            threshold = params.get("threshold", 0)
            value = state.get("value", 0)
            if value >= threshold:
                return True, f"Value {value} meets threshold {threshold}", None
            return False, f"Value {value} below threshold {threshold}", None

        enforcer.register_custom_gate("threshold_check", custom_validator)

        result = enforcer.evaluate(
            gate_id="gate-custom",
            gate_type="threshold_check",
            parameters={"threshold": 10},
            state={"value": 15}
        )

        assert result.passed

    def test_unknown_gate_type_fails(self):
        """Unknown gate type fails with clear message."""
        enforcer = GateEnforcer()

        result = enforcer.evaluate(
            gate_id="gate-unknown",
            gate_type="nonexistent_gate_type",
            parameters={},
            state={}
        )

        assert not result.passed
        assert "unknown" in result.reason.lower()


class TestGateResultDeterminism:
    """Gate result determinism tests."""

    def test_gate_result_to_dict(self):
        """GateResult.to_dict produces consistent output."""
        result = GateResult(
            gate_id="gate-1",
            gate_type="artifact_exists",
            passed=False,
            reason="Artifact not found",
            evaluated_at="2026-01-20T00:00:00Z",
            details={"checked": True}
        )

        d = result.to_dict()

        assert d["gate_id"] == "gate-1"
        assert d["gate_type"] == "artifact_exists"
        assert d["passed"] is False
        assert d["reason"] == "Artifact not found"
        assert d["details"]["checked"] is True
