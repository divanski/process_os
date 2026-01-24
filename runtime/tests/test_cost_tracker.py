"""
ProcessOS Cost Tracker Tests

Sprint 3, Story S3-004: Cost Tracking
TDD tests for CostTracker class - per-request and per-run cost tracking.
"""



class TestCostRecord:
    """Tests for CostRecord dataclass."""

    def test_cost_record_has_required_fields(self):
        """CostRecord should have token counts, model, timestamp, and cost."""
        from cost_tracker import CostRecord

        record = CostRecord(
            input_tokens=100,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            timestamp="2026-01-20T12:00:00Z",
            estimated_cost_usd=0.0033
        )

        assert record.input_tokens == 100
        assert record.output_tokens == 200
        assert record.model == "claude-sonnet-4-20250514"
        assert record.timestamp == "2026-01-20T12:00:00Z"
        assert record.estimated_cost_usd == 0.0033


class TestCostTrackerRecord:
    """Tests for AC1: Cost tracked per request."""

    def test_record_stores_cost(self):
        """record() stores cost for a run_id."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        tracker.record(
            run_id="run_1",
            input_tokens=100,
            output_tokens=200,
            model="claude-sonnet-4-20250514"
        )

        # Should have one record for run_1
        assert tracker.get_call_count("run_1") == 1

    def test_record_multiple_calls_same_run(self):
        """Multiple records for same run_id are tracked."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        tracker.record("run_1", 100, 200, "claude-sonnet-4-20250514")
        tracker.record("run_1", 150, 300, "claude-sonnet-4-20250514")
        tracker.record("run_1", 50, 100, "claude-sonnet-4-20250514")

        assert tracker.get_call_count("run_1") == 3

    def test_record_multiple_runs(self):
        """Records for different run_ids are tracked separately."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        tracker.record("run_1", 100, 200, "claude-sonnet-4-20250514")
        tracker.record("run_2", 150, 300, "claude-sonnet-4-20250514")

        assert tracker.get_call_count("run_1") == 1
        assert tracker.get_call_count("run_2") == 1

    def test_record_calculates_estimated_cost(self):
        """record() calculates estimated cost based on model pricing."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        tracker.record("run_1", 1000, 1000, "claude-sonnet-4-20250514")

        # Sonnet 4: $0.003/1k input, $0.015/1k output
        # 1000 input = $0.003, 1000 output = $0.015 = $0.018 total
        total = tracker.get_run_total("run_1")
        assert abs(total["estimated_cost_usd"] - 0.018) < 0.0001


class TestCostTrackerRunTotal:
    """Tests for AC2: Cost queryable per run."""

    def test_get_run_total_returns_summary(self):
        """get_run_total() returns token sums and cost."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        tracker.record("run_1", 100, 200, "claude-sonnet-4-20250514")
        tracker.record("run_1", 150, 300, "claude-sonnet-4-20250514")

        total = tracker.get_run_total("run_1")

        assert total["run_id"] == "run_1"
        assert total["total_input_tokens"] == 250
        assert total["total_output_tokens"] == 500
        assert total["call_count"] == 2
        assert "estimated_cost_usd" in total

    def test_get_run_total_unknown_run_returns_zeros(self):
        """get_run_total() for unknown run_id returns zeros."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        total = tracker.get_run_total("nonexistent")

        assert total["run_id"] == "nonexistent"
        assert total["total_input_tokens"] == 0
        assert total["total_output_tokens"] == 0
        assert total["call_count"] == 0
        assert total["estimated_cost_usd"] == 0.0

    def test_get_run_total_with_different_models(self):
        """get_run_total() correctly sums costs from different models."""
        from cost_tracker import CostTracker

        tracker = CostTracker()
        # Sonnet call
        tracker.record("run_1", 1000, 1000, "claude-sonnet-4-20250514")
        # Haiku call (cheaper)
        tracker.record("run_1", 1000, 1000, "claude-haiku-35-20241022")

        total = tracker.get_run_total("run_1")

        # Sonnet: $0.003 + $0.015 = $0.018
        # Haiku: $0.00025 + $0.00125 = $0.0015
        # Total: $0.0195
        assert total["call_count"] == 2
        assert abs(total["estimated_cost_usd"] - 0.0195) < 0.0001


class TestModelPricing:
    """Tests for model pricing calculations."""

    def test_sonnet_pricing(self):
        """Sonnet 4 pricing is $0.003/1k input, $0.015/1k output."""
        from cost_tracker import calculate_cost

        # 1000 input tokens, 1000 output tokens
        cost = calculate_cost(1000, 1000, "claude-sonnet-4-20250514")
        assert abs(cost - 0.018) < 0.0001

    def test_haiku_pricing(self):
        """Haiku 3.5 pricing is $0.00025/1k input, $0.00125/1k output."""
        from cost_tracker import calculate_cost

        cost = calculate_cost(1000, 1000, "claude-haiku-35-20241022")
        assert abs(cost - 0.0015) < 0.0001

    def test_unknown_model_uses_sonnet_pricing(self):
        """Unknown model falls back to Sonnet pricing (conservative)."""
        from cost_tracker import calculate_cost

        cost = calculate_cost(1000, 1000, "unknown-model")
        # Should use Sonnet pricing as fallback
        assert abs(cost - 0.018) < 0.0001

    def test_zero_tokens_returns_zero_cost(self):
        """Zero tokens should return zero cost."""
        from cost_tracker import calculate_cost

        cost = calculate_cost(0, 0, "claude-sonnet-4-20250514")
        assert cost == 0.0


class TestCostTrackerIntegration:
    """Integration tests for cost tracking."""

    def test_tracker_with_agent_response(self):
        """CostTracker can be used with AgentResponse usage data."""
        from cost_tracker import CostTracker

        # Simulate what we'd get from AgentResponse.usage
        usage = {"input_tokens": 150, "output_tokens": 300}
        model = "claude-sonnet-4-20250514"

        tracker = CostTracker()
        tracker.record("run_1", usage["input_tokens"], usage["output_tokens"], model)

        total = tracker.get_run_total("run_1")
        assert total["total_input_tokens"] == 150
        assert total["total_output_tokens"] == 300

    def test_global_tracker_singleton(self):
        """get_global_tracker() returns the same instance."""
        from cost_tracker import get_global_tracker

        tracker1 = get_global_tracker()
        tracker2 = get_global_tracker()

        assert tracker1 is tracker2
