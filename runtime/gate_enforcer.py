"""
ProcessOS Gate Enforcer

Enforces gate conditions with hard halts on failure.
All gate results are deterministic given the same state.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable

from .artifact_registry import ArtifactRegistry


@dataclass
class GateResult:
    """Result of gate evaluation."""
    gate_id: str
    gate_type: str
    passed: bool
    reason: str
    evaluated_at: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "gate_id": self.gate_id,
            "gate_type": self.gate_type,
            "passed": self.passed,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at,
        }
        if self.details:
            result["details"] = self.details
        return result


class GateEnforcer:
    """
    Evaluates and enforces gate conditions.

    Gate Types:
    - artifact_exists: Check if artifact of specific kind exists
    - all_artifacts_present: Check multiple artifacts exist
    - field_value: Check field has expected value
    - custom: User-defined validation function

    All failures result in deterministic halt with reason.
    """

    def __init__(self, artifact_registry: Optional[ArtifactRegistry] = None):
        """
        Initialize enforcer.

        Args:
            artifact_registry: Registry to check artifact existence
        """
        self.artifact_registry = artifact_registry
        self._custom_gates: Dict[str, Callable] = {}
        self._results: List[GateResult] = []

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def register_custom_gate(self, gate_type: str, evaluator: Callable) -> None:
        """
        Register a custom gate evaluator.

        Args:
            gate_type: Gate type name
            evaluator: Function(state, parameters) -> (passed, reason)
        """
        self._custom_gates[gate_type] = evaluator

    def evaluate(
        self,
        gate_id: str,
        gate_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> GateResult:
        """
        Evaluate a gate condition.

        Args:
            gate_id: Unique gate identifier
            gate_type: Type of gate to evaluate
            parameters: Gate-specific parameters
            state: Current run state

        Returns:
            GateResult with pass/fail and reason
        """
        evaluator = self._get_evaluator(gate_type)
        passed, reason, details = evaluator(parameters, state)

        result = GateResult(
            gate_id=gate_id,
            gate_type=gate_type,
            passed=passed,
            reason=reason,
            evaluated_at=self._now(),
            details=details,
        )

        self._results.append(result)
        return result

    def _get_evaluator(self, gate_type: str) -> Callable:
        """Get evaluator function for gate type."""
        built_in = {
            "artifact_exists": self._eval_artifact_exists,
            "all_artifacts_present": self._eval_all_artifacts_present,
            "field_value": self._eval_field_value,
            "step_completed": self._eval_step_completed,
        }

        if gate_type in built_in:
            return built_in[gate_type]
        elif gate_type in self._custom_gates:
            return self._custom_gates[gate_type]
        else:
            return lambda p, s: (False, f"Unknown gate type: {gate_type}", None)

    def _eval_artifact_exists(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> tuple[bool, str, Optional[Dict]]:
        """Evaluate artifact_exists gate."""
        artifact_kind = parameters.get("artifact_kind")
        if not artifact_kind:
            return False, "artifact_kind parameter required", None

        # Check in artifact registry
        if self.artifact_registry:
            artifacts = self.artifact_registry.find_by_kind(artifact_kind)
            if artifacts:
                return True, f"Artifact of kind '{artifact_kind}' exists", {
                    "artifact_id": artifacts[0].artifact_id,
                    "sha256": artifacts[0].sha256,
                }

        # Check in state artifacts
        state_artifacts = state.get("artifacts", [])
        for artifact in state_artifacts:
            if artifact.get("artifact_kind") == artifact_kind:
                return True, f"Artifact of kind '{artifact_kind}' found in state", {
                    "artifact_id": artifact.get("artifact_id"),
                }

        return False, f"Artifact of kind '{artifact_kind}' not found", {
            "checked_registry": self.artifact_registry is not None,
            "state_artifact_count": len(state_artifacts),
        }

    def _eval_all_artifacts_present(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> tuple[bool, str, Optional[Dict]]:
        """Evaluate all_artifacts_present gate."""
        required = parameters.get("required_artifacts", [])
        if not required:
            return True, "No artifacts required", None

        missing = []
        found = []

        for kind in required:
            # Check registry
            if self.artifact_registry:
                artifacts = self.artifact_registry.find_by_kind(kind)
                if artifacts:
                    found.append(kind)
                    continue

            # Check state
            state_artifacts = state.get("artifacts", [])
            if any(a.get("artifact_kind") == kind for a in state_artifacts):
                found.append(kind)
                continue

            missing.append(kind)

        if missing:
            return False, f"Missing artifacts: {', '.join(sorted(missing))}", {
                "missing": sorted(missing),
                "found": sorted(found),
            }

        return True, f"All {len(required)} required artifacts present", {
            "found": sorted(found),
        }

    def _eval_field_value(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> tuple[bool, str, Optional[Dict]]:
        """Evaluate field_value gate."""
        field_path = parameters.get("field")
        expected = parameters.get("expected")

        if not field_path:
            return False, "field parameter required", None

        # Navigate to field
        current = state
        path_parts = field_path.split(".")
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False, f"Field '{field_path}' not found", {
                    "path": field_path,
                    "missing_at": part,
                }

        if current == expected:
            return True, f"Field '{field_path}' equals expected value", {
                "field": field_path,
                "value": current,
            }

        return False, f"Field '{field_path}' has unexpected value", {
            "field": field_path,
            "expected": expected,
            "actual": current,
        }

    def _eval_step_completed(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> tuple[bool, str, Optional[Dict]]:
        """Evaluate step_completed gate."""
        step_id = parameters.get("step_id")
        if not step_id:
            return False, "step_id parameter required", None

        steps = state.get("steps", [])
        for step in steps:
            if step.get("step_id") == step_id:
                if step.get("status") == "completed":
                    return True, f"Step '{step_id}' is completed", {
                        "step_id": step_id,
                        "status": "completed",
                    }
                else:
                    return False, f"Step '{step_id}' not completed (status: {step.get('status')})", {
                        "step_id": step_id,
                        "status": step.get("status"),
                    }

        return False, f"Step '{step_id}' not found", {
            "step_id": step_id,
            "available_steps": [s.get("step_id") for s in steps],
        }

    def check_all(
        self,
        gates: List[Dict[str, Any]],
        state: Dict[str, Any]
    ) -> tuple[bool, List[GateResult]]:
        """
        Evaluate all gates and return combined result.

        Args:
            gates: List of gate definitions
            state: Current run state

        Returns:
            Tuple of (all_passed, list of results)
        """
        results = []
        all_passed = True

        for gate in gates:
            result = self.evaluate(
                gate_id=gate.get("gate_id", "unknown"),
                gate_type=gate.get("gate_type", "unknown"),
                parameters=gate.get("parameters", {}),
                state=state,
            )
            results.append(result)
            if not result.passed:
                all_passed = False
                # Halt-only routing: stop on first failure
                break

        return all_passed, results

    def get_results(self) -> List[GateResult]:
        """Get all evaluation results."""
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear evaluation results."""
        self._results.clear()

    def get_failed_reasons(self) -> List[str]:
        """Get reasons for all failed gates."""
        return [r.reason for r in self._results if not r.passed]
