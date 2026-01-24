"""
ProcessOS View Isolation Tests

Tests for SN-004 and SN-010:
- Agent views contain only declared inputs
- Undeclared inputs are rejected
- Budget limits enforced
"""

import pytest
import sys
from pathlib import Path

# Add process_os to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from process_os.runtime.context_budgeter import ContextBudgeter, ViewBudget, ContextViolation


class TestViewIsolation:
    """View isolation tests."""

    def test_declared_input_accepted(self):
        """Declared inputs are accepted."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["input_a", "input_b"])

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"input_a": "value_a", "input_b": "value_b"}
        )

        assert is_valid
        assert len(violations) == 0

    def test_undeclared_input_rejected(self):
        """Undeclared inputs are rejected."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["input_a"])

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"input_a": "value_a", "undeclared_input": "value_x"}
        )

        assert not is_valid
        assert len(violations) == 1
        assert violations[0].violation_type == "undeclared_input"
        assert violations[0].input_name == "undeclared_input"

    def test_multiple_undeclared_inputs_rejected(self):
        """Multiple undeclared inputs all generate violations."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["input_a"])

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"input_a": "ok", "bad_1": "x", "bad_2": "y", "bad_3": "z"}
        )

        assert not is_valid
        assert len(violations) == 3

        violation_inputs = {v.input_name for v in violations}
        assert violation_inputs == {"bad_1", "bad_2", "bad_3"}

    def test_no_declarations_rejects_all(self):
        """Step with no declarations rejects all inputs."""
        budgeter = ContextBudgeter()
        # No declarations for step-1

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"any_input": "value"}
        )

        assert not is_valid
        assert len(violations) == 1


class TestViewFiltering:
    """View filtering tests."""

    def test_filter_removes_undeclared(self):
        """Filter removes undeclared inputs."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["allowed_1", "allowed_2"])

        filtered = budgeter.filter_view(
            "step-1",
            {"allowed_1": "a", "allowed_2": "b", "not_allowed": "c"}
        )

        assert "allowed_1" in filtered
        assert "allowed_2" in filtered
        assert "not_allowed" not in filtered
        assert len(filtered) == 2

    def test_filter_empty_when_no_declarations(self):
        """Filter returns empty dict when no declarations."""
        budgeter = ContextBudgeter()

        filtered = budgeter.filter_view("step-1", {"any": "value"})

        assert filtered == {}


class TestBudgetLimits:
    """Budget enforcement tests."""

    def test_artifact_size_limit(self):
        """Artifact size limit is enforced."""
        budgeter = ContextBudgeter(ViewBudget(max_artifact_size=100))
        budgeter.declare_inputs("step-1", ["big_input"])

        large_content = "x" * 200  # Exceeds 100 limit

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"big_input": large_content}
        )

        assert not is_valid
        assert any(v.violation_type == "artifact_too_large" for v in violations)

    def test_artifact_count_limit(self):
        """Artifact count limit is enforced."""
        budgeter = ContextBudgeter(ViewBudget(max_artifacts=2))
        budgeter.declare_inputs("step-1", ["a", "b", "c", "d"])

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"a": "1", "b": "2", "c": "3", "d": "4"}
        )

        assert not is_valid
        assert any(
            v.violation_type == "budget_exceeded" and "count" in v.details.lower()
            for v in violations
        )

    def test_token_limit(self):
        """Token limit is enforced."""
        budgeter = ContextBudgeter(ViewBudget(max_tokens=10))
        budgeter.declare_inputs("step-1", ["input"])

        # ~4 chars per token, so 100 chars = ~25 tokens > 10
        content = "x" * 100

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"input": content}
        )

        assert not is_valid
        assert any(
            v.violation_type == "budget_exceeded" and "token" in v.details.lower()
            for v in violations
        )

    def test_within_budget_passes(self):
        """Content within all limits passes."""
        budgeter = ContextBudgeter(ViewBudget(
            max_tokens=10000,
            max_artifacts=10,
            max_artifact_size=10000
        ))
        budgeter.declare_inputs("step-1", ["input"])

        is_valid, violations = budgeter.validate_view(
            "step-1",
            {"input": "small content"}
        )

        assert is_valid
        assert len(violations) == 0


class TestViolationTracking:
    """Violation tracking tests."""

    def test_violations_accumulated(self):
        """Violations are accumulated across calls."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["a"])
        budgeter.declare_inputs("step-2", ["b"])

        budgeter.validate_view("step-1", {"a": "ok", "bad": "x"})
        budgeter.validate_view("step-2", {"b": "ok", "also_bad": "y"})

        violations = budgeter.get_violations()
        assert len(violations) == 2

    def test_clear_violations(self):
        """Violations can be cleared."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["a"])

        budgeter.validate_view("step-1", {"bad": "x"})
        assert len(budgeter.get_violations()) == 1

        budgeter.clear_violations()
        assert len(budgeter.get_violations()) == 0


class TestDeclaredInputsManagement:
    """Declared inputs management tests."""

    def test_get_declared_inputs(self):
        """Can retrieve declared inputs for a step."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["a", "b", "c"])

        declared = budgeter.get_declared_inputs("step-1")

        assert declared == {"a", "b", "c"}

    def test_declared_inputs_isolated_per_step(self):
        """Declarations are isolated per step."""
        budgeter = ContextBudgeter()
        budgeter.declare_inputs("step-1", ["a", "b"])
        budgeter.declare_inputs("step-2", ["c", "d"])

        assert budgeter.is_declared("step-1", "a")
        assert not budgeter.is_declared("step-1", "c")
        assert budgeter.is_declared("step-2", "c")
        assert not budgeter.is_declared("step-2", "a")
