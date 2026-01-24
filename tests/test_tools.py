"""
ProcessOS Tools Tests

Tests for Sprint 6: Tool policy enforcement.
"""

from pathlib import Path

import pytest

from process_os.tools import ToolRegistry, ToolPolicy, ToolsDisabledError


class TestToolPolicy:
    """Test tool policy loading and validation."""

    def test_default_policy_disabled(self):
        """Default policy has tools disabled."""
        policy = ToolPolicy.default()
        assert policy.enabled is False
        assert policy.require_explicit_opt_in is True

    def test_policy_from_yaml(self):
        """Can load policy from YAML file."""
        policy_path = Path(__file__).parent.parent / "tools" / "tool_policy.yaml"
        policy = ToolPolicy.from_yaml(policy_path)

        # Policy should be disabled by default
        assert policy.enabled is False
        assert len(policy.allowlist) > 0
        assert len(policy.denylist) > 0

    def test_policy_denies_file_write(self):
        """Policy denies file_write tool."""
        policy_path = Path(__file__).parent.parent / "tools" / "tool_policy.yaml"
        policy = ToolPolicy.from_yaml(policy_path)

        # Tools are disabled, so file_write is not allowed
        assert policy.is_allowed("file_write") is False
        # When disabled, reason is about policy being disabled
        reason = policy.get_denial_reason("file_write")
        assert "disabled" in reason.lower()

    def test_policy_denies_shell_exec(self):
        """Policy denies shell_exec tool."""
        policy_path = Path(__file__).parent.parent / "tools" / "tool_policy.yaml"
        policy = ToolPolicy.from_yaml(policy_path)

        assert policy.is_allowed("shell_exec") is False


class TestToolRegistry:
    """Test tool registry behavior."""

    def test_tools_disabled_by_default(self):
        """Tools are disabled by default."""
        registry = ToolRegistry()

        with pytest.raises(ToolsDisabledError):
            registry.call("file_read")

    def test_registry_is_enabled_false(self):
        """Registry reports disabled state."""
        registry = ToolRegistry()
        assert registry.is_enabled() is False

    def test_registry_from_policy_file(self):
        """Can create registry from policy file."""
        policy_path = Path(__file__).parent.parent / "tools" / "tool_policy.yaml"
        registry = ToolRegistry.from_policy_file(policy_path)

        assert registry.is_enabled() is False

    def test_registry_lists_available_tools(self):
        """Registry lists tools that would be available."""
        policy_path = Path(__file__).parent.parent / "tools" / "tool_policy.yaml"
        registry = ToolRegistry.from_policy_file(policy_path)

        available = registry.list_available()
        assert "file_read" in available
        assert "http_fetch" in available

    def test_disabled_registry_rejects_all_calls(self):
        """Disabled registry rejects all tool calls."""
        registry = ToolRegistry()

        # Register a tool
        registry.register(
            "test_tool",
            "Test tool",
            handler=lambda: "result",
        )

        # Should still reject because policy is disabled
        with pytest.raises(ToolsDisabledError):
            registry.call("test_tool")

    def test_audit_log_records_denials(self):
        """Audit log records denied calls."""
        registry = ToolRegistry()

        try:
            registry.call("file_read")
        except ToolsDisabledError:
            pass

        log = registry.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "denied"
        assert log[0]["tool_id"] == "file_read"
