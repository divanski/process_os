"""
ProcessOS Cost Tracker

Sprint 3, Story S3-004: Cost Tracking
Tracks per-request and per-run costs for agent invocations.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

__all__ = [
    "CostTracker",
    "CostRecord",
    "calculate_cost",
    "get_global_tracker",
]

# Model pricing table (per 1000 tokens)
# Sprint 3: hardcoded, configurable in future
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {
        "input_per_1k": 0.003,
        "output_per_1k": 0.015
    },
    "claude-haiku-35-20241022": {
        "input_per_1k": 0.00025,
        "output_per_1k": 0.00125
    },
    # Add more models as needed
}

# Default pricing (use Sonnet as conservative fallback)
DEFAULT_PRICING = MODEL_PRICING["claude-sonnet-4-20250514"]


@dataclass
class CostRecord:
    """Record of a single agent call's cost.

    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model identifier
        timestamp: ISO timestamp of the record
        estimated_cost_usd: Estimated cost in USD
    """
    input_tokens: int
    output_tokens: int
    model: str
    timestamp: str
    estimated_cost_usd: float


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate estimated cost for an agent call.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model identifier

    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * pricing["output_per_1k"]

    return input_cost + output_cost


class CostTracker:
    """Tracks costs for agent invocations per run.

    Stores costs in memory. Not thread-safe - intended for single-threaded use.
    """

    def __init__(self):
        """Initialize the cost tracker with empty storage."""
        self._costs: Dict[str, List[CostRecord]] = {}

    def record(
        self,
        run_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> CostRecord:
        """Record cost for a single agent call.

        Args:
            run_id: The run identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model identifier

        Returns:
            The created CostRecord
        """
        estimated_cost = calculate_cost(input_tokens, output_tokens, model)
        timestamp = datetime.now(timezone.utc).isoformat()

        record = CostRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            timestamp=timestamp,
            estimated_cost_usd=estimated_cost
        )

        if run_id not in self._costs:
            self._costs[run_id] = []

        self._costs[run_id].append(record)
        return record

    def get_call_count(self, run_id: str) -> int:
        """Get the number of recorded calls for a run.

        Args:
            run_id: The run identifier

        Returns:
            Number of recorded calls
        """
        return len(self._costs.get(run_id, []))

    def get_run_total(self, run_id: str) -> Dict[str, Any]:
        """Get total cost summary for a run.

        Args:
            run_id: The run identifier

        Returns:
            Dict with run_id, token totals, call_count, and estimated_cost_usd
        """
        records = self._costs.get(run_id, [])

        if not records:
            return {
                "run_id": run_id,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "call_count": 0,
                "estimated_cost_usd": 0.0
            }

        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_cost = sum(r.estimated_cost_usd for r in records)

        return {
            "run_id": run_id,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "call_count": len(records),
            "estimated_cost_usd": total_cost
        }

    def get_records(self, run_id: str) -> List[CostRecord]:
        """Get all cost records for a run.

        Args:
            run_id: The run identifier

        Returns:
            List of CostRecord objects
        """
        return list(self._costs.get(run_id, []))

    def clear(self, run_id: Optional[str] = None) -> None:
        """Clear cost records.

        Args:
            run_id: If provided, clear only that run. Otherwise clear all.
        """
        if run_id:
            self._costs.pop(run_id, None)
        else:
            self._costs.clear()


# Global tracker instance (singleton pattern)
_global_tracker: Optional[CostTracker] = None


def get_global_tracker() -> CostTracker:
    """Get the global CostTracker singleton.

    Returns:
        The global CostTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker
