"""
ProcessOS Tool Registry

Manages tool availability with strict policy enforcement.
Tools are DISABLED by default.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml


class ToolsDisabledError(Exception):
    """Raised when tools are called but disabled."""

    pass


class ToolDeniedError(Exception):
    """Raised when a specific tool is denied."""

    pass


@dataclass
class ToolDefinition:
    """Definition of an available tool."""

    tool_id: str
    description: str
    risk_level: str
    handler: Optional[Callable] = None
    constraints: List[str] = field(default_factory=list)


@dataclass
class ToolPolicy:
    """Tool policy configuration."""

    enabled: bool = False
    require_explicit_opt_in: bool = True
    audit_all_calls: bool = True
    max_calls_per_run: int = 100

    allowlist: List[Dict[str, Any]] = field(default_factory=list)
    denylist: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "ToolPolicy":
        """Load policy from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        policy_data = data.get("policy", {})
        return cls(
            enabled=policy_data.get("enabled", False),
            require_explicit_opt_in=policy_data.get("require_explicit_opt_in", True),
            audit_all_calls=policy_data.get("audit_all_calls", True),
            max_calls_per_run=policy_data.get("max_calls_per_run", 100),
            allowlist=data.get("allowlist", []),
            denylist=data.get("denylist", []),
        )

    @classmethod
    def default(cls) -> "ToolPolicy":
        """Get default policy (tools disabled)."""
        return cls(enabled=False)

    def is_allowed(self, tool_id: str) -> bool:
        """Check if a tool is allowed by policy."""
        if not self.enabled:
            return False

        # Check denylist first
        for denied in self.denylist:
            if denied.get("tool_id") == tool_id:
                return False

        # Check allowlist
        for allowed in self.allowlist:
            if allowed.get("tool_id") == tool_id:
                return True

        return False

    def get_denial_reason(self, tool_id: str) -> Optional[str]:
        """Get reason why a tool is denied."""
        if not self.enabled:
            return "Tools are disabled by policy"

        for denied in self.denylist:
            if denied.get("tool_id") == tool_id:
                return denied.get("reason", "Tool is on denylist")

        return None


class ToolRegistry:
    """
    Registry of available tools with policy enforcement.

    Tools are DISABLED by default and require explicit policy opt-in.
    """

    def __init__(self, policy: Optional[ToolPolicy] = None):
        """
        Initialize tool registry.

        Args:
            policy: Tool policy (defaults to disabled)
        """
        self.policy = policy or ToolPolicy.default()
        self._tools: Dict[str, ToolDefinition] = {}
        self._call_count = 0
        self._audit_log: List[Dict[str, Any]] = []

    @classmethod
    def from_policy_file(cls, policy_path: Path) -> "ToolRegistry":
        """Create registry from policy file."""
        policy = ToolPolicy.from_yaml(policy_path)
        return cls(policy)

    def register(
        self,
        tool_id: str,
        description: str,
        handler: Callable,
        risk_level: str = "medium",
    ) -> None:
        """
        Register a tool handler.

        Note: Registration does not enable the tool.
        Tool must also be in policy allowlist and policy must be enabled.
        """
        self._tools[tool_id] = ToolDefinition(
            tool_id=tool_id,
            description=description,
            risk_level=risk_level,
            handler=handler,
        )

    def call(self, tool_id: str, **kwargs) -> Any:
        """
        Call a tool if allowed by policy.

        Args:
            tool_id: Tool to call
            **kwargs: Tool arguments

        Returns:
            Tool result

        Raises:
            ToolsDisabledError: If tools are disabled
            ToolDeniedError: If specific tool is denied
        """
        # Check policy first
        if not self.policy.enabled:
            self._audit("denied", tool_id, "Tools disabled")
            raise ToolsDisabledError("Tools are disabled by policy")

        if not self.policy.is_allowed(tool_id):
            reason = self.policy.get_denial_reason(tool_id) or "Not in allowlist"
            self._audit("denied", tool_id, reason)
            raise ToolDeniedError(f"Tool '{tool_id}' denied: {reason}")

        # Check call limit
        if self._call_count >= self.policy.max_calls_per_run:
            self._audit("denied", tool_id, "Call limit exceeded")
            raise ToolDeniedError(f"Tool call limit exceeded ({self.policy.max_calls_per_run})")

        # Check tool is registered
        tool = self._tools.get(tool_id)
        if tool is None or tool.handler is None:
            self._audit("denied", tool_id, "Tool not registered")
            raise ToolDeniedError(f"Tool '{tool_id}' not registered")

        # Execute tool
        self._call_count += 1
        self._audit("allowed", tool_id, "Executed")

        return tool.handler(**kwargs)

    def _audit(self, action: str, tool_id: str, reason: str) -> None:
        """Record audit entry."""
        if self.policy.audit_all_calls:
            self._audit_log.append({
                "action": action,
                "tool_id": tool_id,
                "reason": reason,
                "call_count": self._call_count,
            })

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        return list(self._audit_log)

    def is_enabled(self) -> bool:
        """Check if tools are enabled."""
        return self.policy.enabled

    def list_available(self) -> List[str]:
        """List tools that would be available if enabled."""
        return [t["tool_id"] for t in self.policy.allowlist]

    def reset_call_count(self) -> None:
        """Reset call count for new run."""
        self._call_count = 0
