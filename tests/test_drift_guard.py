"""
ProcessOS Drift Guard Tests

Tests for Sprint 8: Drift guard enforcement.
"""

from pathlib import Path

import pytest

from process_os.drift import (
    DriftGuard,
    DriftViolationError,
    GateViolation,
    WriteViolation,
)


class TestWriteAllowlist:
    """Test write allowlist enforcement."""

    def test_allows_processos_directory(self, tmp_path: Path):
        """Allows writes to .processos/ directory."""
        guard = DriftGuard(tmp_path)

        # Should not raise
        guard.check_write(tmp_path / ".processos" / "binding.yaml")
        guard.check_write(tmp_path / ".processos" / "runs" / "run-1" / "state.yaml")

    def test_blocks_outside_allowlist(self, tmp_path: Path):
        """Blocks writes outside allowlist."""
        guard = DriftGuard(tmp_path)

        with pytest.raises(WriteViolation):
            guard.check_write(tmp_path / "src" / "main.py")

    def test_blocks_parent_directory(self, tmp_path: Path):
        """Blocks writes to parent directory."""
        guard = DriftGuard(tmp_path)

        with pytest.raises(WriteViolation):
            guard.check_write(tmp_path.parent / "other_project" / "file.txt")

    def test_custom_allowlist(self, tmp_path: Path):
        """Respects custom allowlist."""
        guard = DriftGuard(tmp_path, allowlist=[".custom/**"])

        # Should allow
        guard.check_write(tmp_path / ".custom" / "file.txt")

        # Should block .processos now
        with pytest.raises(WriteViolation):
            guard.check_write(tmp_path / ".processos" / "binding.yaml")

    def test_is_path_allowed_no_raise(self, tmp_path: Path):
        """is_path_allowed returns bool without raising."""
        guard = DriftGuard(tmp_path)

        assert guard.is_path_allowed(tmp_path / ".processos" / "test.yaml") is True
        assert guard.is_path_allowed(tmp_path / "src" / "main.py") is False

    def test_violation_contains_details(self, tmp_path: Path):
        """WriteViolation contains path and allowlist details."""
        guard = DriftGuard(tmp_path)

        try:
            guard.check_write(tmp_path / "forbidden.txt")
            pytest.fail("Should have raised WriteViolation")
        except WriteViolation as e:
            assert e.violation_type == "write_violation"
            assert "forbidden.txt" in str(e.details["path"])
            assert ".processos/**" in e.details["allowlist"]


class TestGateEnforcement:
    """Test gate enforcement."""

    def test_passes_successful_gate(self, tmp_path: Path):
        """Allows execution when gate passes."""
        guard = DriftGuard(tmp_path)

        # Should not raise
        guard.check_gate("validation-gate", passed=True)

    def test_halts_on_gate_failure(self, tmp_path: Path):
        """Halts execution when gate fails."""
        guard = DriftGuard(tmp_path)

        with pytest.raises(GateViolation):
            guard.check_gate("validation-gate", passed=False, reason="Schema invalid")

    def test_gate_violation_contains_details(self, tmp_path: Path):
        """GateViolation contains gate ID and reason."""
        guard = DriftGuard(tmp_path)

        try:
            guard.check_gate("test-gate", passed=False, reason="Test failure")
            pytest.fail("Should have raised GateViolation")
        except GateViolation as e:
            assert e.violation_type == "gate_failure"
            assert e.details["gate_id"] == "test-gate"
            assert e.details["reason"] == "Test failure"


class TestEventRecording:
    """Test drift event recording."""

    def test_records_check_events(self, tmp_path: Path):
        """Records all check events."""
        guard = DriftGuard(tmp_path)

        guard.check_write(tmp_path / ".processos" / "test.yaml")
        guard.check_gate("gate-1", passed=True)

        events = guard.get_events()
        assert len(events) == 2
        assert events[0].check_type == "write"
        assert events[1].check_type == "gate"

    def test_records_violations(self, tmp_path: Path):
        """Records violation events."""
        guard = DriftGuard(tmp_path)

        try:
            guard.check_write(tmp_path / "forbidden.txt")
        except WriteViolation:
            pass

        violations = guard.get_violations()
        assert len(violations) == 1
        assert violations[0].allowed is False

    def test_clear_events(self, tmp_path: Path):
        """Can clear recorded events."""
        guard = DriftGuard(tmp_path)

        guard.check_write(tmp_path / ".processos" / "test.yaml")
        assert len(guard.get_events()) == 1

        guard.clear_events()
        assert len(guard.get_events()) == 0


class TestViolationSerialization:
    """Test violation serialization."""

    def test_violation_to_dict(self, tmp_path: Path):
        """Violation converts to dictionary."""
        guard = DriftGuard(tmp_path)

        try:
            guard.check_write(tmp_path / "forbidden.txt")
        except WriteViolation as e:
            d = e.to_dict()
            assert "violation_type" in d
            assert "message" in d
            assert "details" in d
            assert "timestamp" in d
