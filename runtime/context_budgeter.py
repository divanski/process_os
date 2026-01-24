"""
ProcessOS Context Budgeter

Enforces view size limits and rejects undeclared inputs.
Prevents context drift by strictly controlling what agents can see.
"""

import json
from dataclasses import dataclass
from typing import Dict, List, Set, Any, Optional


@dataclass
class ViewBudget:
    """Budget configuration for a view."""
    max_tokens: int = 100000  # Default max context
    max_artifacts: int = 10
    max_artifact_size: int = 50000  # Per artifact


@dataclass
class ContextViolation:
    """Record of a context violation."""
    violation_type: str  # undeclared_input, budget_exceeded, artifact_too_large
    input_name: str
    details: str


class ContextBudgeter:
    """
    Enforces context isolation and budget limits.

    Features:
    - Declare allowed inputs per step
    - Reject undeclared inputs
    - Enforce token/size limits
    - Track violations
    """

    def __init__(self, budget: Optional[ViewBudget] = None):
        """
        Initialize budgeter.

        Args:
            budget: Budget configuration (uses defaults if None)
        """
        self.budget = budget or ViewBudget()
        self._declared_inputs: Dict[str, Set[str]] = {}  # step_id -> set of input names
        self._violations: List[ContextViolation] = []

    def declare_inputs(self, step_id: str, input_names: List[str]) -> None:
        """
        Declare allowed inputs for a step.

        Args:
            step_id: Step identifier
            input_names: List of allowed input names
        """
        self._declared_inputs[step_id] = set(input_names)

    def is_declared(self, step_id: str, input_name: str) -> bool:
        """
        Check if input is declared for step.

        Args:
            step_id: Step identifier
            input_name: Input to check

        Returns:
            True if declared, False otherwise
        """
        if step_id not in self._declared_inputs:
            return False
        return input_name in self._declared_inputs[step_id]

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        return len(content) // 4

    def validate_view(
        self,
        step_id: str,
        inputs: Dict[str, Any],
        strict: bool = True
    ) -> tuple[bool, List[ContextViolation]]:
        """
        Validate a view against declarations and budget.

        Args:
            step_id: Step identifier
            inputs: Dict of input_name -> content
            strict: If True, raise on violation; if False, just record

        Returns:
            Tuple of (is_valid, list of violations)
        """
        violations = []
        declared = self._declared_inputs.get(step_id, set())

        # Check for undeclared inputs
        for input_name in inputs:
            if input_name not in declared:
                violation = ContextViolation(
                    violation_type="undeclared_input",
                    input_name=input_name,
                    details=f"Input '{input_name}' not declared for step '{step_id}'"
                )
                violations.append(violation)

        # Check total size
        total_content = ""
        artifact_count = 0

        for input_name, content in inputs.items():
            if input_name in declared:
                content_str = json.dumps(content) if not isinstance(content, str) else content

                # Check individual artifact size
                if len(content_str) > self.budget.max_artifact_size:
                    violation = ContextViolation(
                        violation_type="artifact_too_large",
                        input_name=input_name,
                        details=f"Input '{input_name}' size {len(content_str)} exceeds max {self.budget.max_artifact_size}"
                    )
                    violations.append(violation)

                total_content += content_str
                artifact_count += 1

        # Check artifact count
        if artifact_count > self.budget.max_artifacts:
            violation = ContextViolation(
                violation_type="budget_exceeded",
                input_name="*",
                details=f"Artifact count {artifact_count} exceeds max {self.budget.max_artifacts}"
            )
            violations.append(violation)

        # Check total tokens
        total_tokens = self._estimate_tokens(total_content)
        if total_tokens > self.budget.max_tokens:
            violation = ContextViolation(
                violation_type="budget_exceeded",
                input_name="*",
                details=f"Estimated tokens {total_tokens} exceeds max {self.budget.max_tokens}"
            )
            violations.append(violation)

        # Record violations
        self._violations.extend(violations)

        return len(violations) == 0, violations

    def filter_view(self, step_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter view to only declared inputs.

        Args:
            step_id: Step identifier
            inputs: Dict of input_name -> content

        Returns:
            Filtered dict with only declared inputs
        """
        declared = self._declared_inputs.get(step_id, set())
        return {k: v for k, v in inputs.items() if k in declared}

    def get_violations(self) -> List[ContextViolation]:
        """Get all recorded violations."""
        return self._violations.copy()

    def clear_violations(self) -> None:
        """Clear recorded violations."""
        self._violations.clear()

    def get_declared_inputs(self, step_id: str) -> Set[str]:
        """Get declared inputs for a step."""
        return self._declared_inputs.get(step_id, set()).copy()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize budgeter state."""
        return {
            "budget": {
                "max_tokens": self.budget.max_tokens,
                "max_artifacts": self.budget.max_artifacts,
                "max_artifact_size": self.budget.max_artifact_size,
            },
            "declared_inputs": {
                step_id: sorted(inputs)
                for step_id, inputs in self._declared_inputs.items()
            },
            "violations": [
                {
                    "violation_type": v.violation_type,
                    "input_name": v.input_name,
                    "details": v.details,
                }
                for v in self._violations
            ],
        }
