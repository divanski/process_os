"""
ProcessOS Host Adapter Interface

Abstract base class defining read-only access to host project files.
"""

import fnmatch
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class HostAccessDenied(Exception):
    """Raised when access to a host path is denied by policy."""

    def __init__(self, message: str, path: str = "", reason: str = ""):
        super().__init__(message)
        self.path = path
        self.reason = reason


@dataclass
class PolicyLimits:
    """Resource limits for host access."""

    max_file_size_kb: int = 500
    max_files_per_query: int = 100
    max_total_size_kb: int = 5000


@dataclass
class HostPolicy:
    """
    Policy configuration for host access control.

    Attributes:
        version: Policy schema version
        mode: Either "allowlist" (default, restrictive) or "denylist" (permissive)
        allowlist_patterns: Glob patterns for allowed paths
        denylist_patterns: Glob patterns for denied paths (always enforced)
        max_depth: Maximum directory depth for traversal
        limits: Resource limits
    """

    version: str = "1.0"
    mode: str = "allowlist"
    allowlist_patterns: List[str] = field(default_factory=list)
    denylist_patterns: List[str] = field(default_factory=list)
    max_depth: int = 10
    limits: PolicyLimits = field(default_factory=PolicyLimits)

    @classmethod
    def from_yaml(cls, path: Path) -> "HostPolicy":
        """Load policy from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        limits_data = data.get("limits", {})
        limits = PolicyLimits(
            max_file_size_kb=limits_data.get("max_file_size_kb", 500),
            max_files_per_query=limits_data.get("max_files_per_query", 100),
            max_total_size_kb=limits_data.get("max_total_size_kb", 5000),
        )

        allowlist = data.get("allowlist", {})
        denylist = data.get("denylist", {})

        return cls(
            version=data.get("version", "1.0"),
            mode=data.get("mode", "allowlist"),
            allowlist_patterns=allowlist.get("patterns", []),
            denylist_patterns=denylist.get("patterns", []),
            max_depth=allowlist.get("max_depth", 10),
            limits=limits,
        )

    @classmethod
    def default(cls) -> "HostPolicy":
        """Create default restrictive policy."""
        return cls(
            version="1.0",
            mode="allowlist",
            allowlist_patterns=[
                "*.py",
                "*.js",
                "*.ts",
                "*.json",
                "*.yaml",
                "*.yml",
                "*.md",
                "*.txt",
                "src/**/*",
                "lib/**/*",
                "tests/**/*",
            ],
            denylist_patterns=[
                ".git/**",
                ".git",
                ".env",
                ".env.*",
                "**/*.key",
                "**/*.pem",
                "**/*.p12",
                "**/secrets/**",
                "**/credentials/**",
                "**/.claude/**",
                "**/node_modules/**",
                "**/__pycache__/**",
                "**/.venv/**",
                "**/venv/**",
            ],
            max_depth=10,
            limits=PolicyLimits(),
        )

    def matches_denylist(self, path: str) -> bool:
        """Check if path matches any denylist pattern."""
        normalized = path.replace("\\", "/")
        for pattern in self.denylist_patterns:
            if fnmatch.fnmatch(normalized, pattern):
                return True
            # Also check if any parent matches
            if "**" in pattern:
                # For ** patterns, check component-wise
                if self._glob_match(normalized, pattern):
                    return True
        return False

    def matches_allowlist(self, path: str) -> bool:
        """Check if path matches any allowlist pattern."""
        normalized = path.replace("\\", "/")
        for pattern in self.allowlist_patterns:
            if fnmatch.fnmatch(normalized, pattern):
                return True
            if "**" in pattern and self._glob_match(normalized, pattern):
                return True
        return False

    def _glob_match(self, path: str, pattern: str) -> bool:
        """Match path against glob pattern with ** support."""
        import re

        # Handle ** at start - it can match empty string
        # e.g., **/credentials/** should match credentials/token.json
        if pattern.startswith("**/"):
            # Try without the **/ prefix too
            rest = pattern[3:]
            if fnmatch.fnmatch(path, rest):
                return True

        # Escape special regex chars except * and ?
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("**", "<<<GLOBSTAR>>>")
        regex_pattern = regex_pattern.replace("*", "[^/]*")
        regex_pattern = regex_pattern.replace("?", ".")
        regex_pattern = regex_pattern.replace("<<<GLOBSTAR>>>", ".*")
        regex_pattern = f"^{regex_pattern}$"

        return bool(re.match(regex_pattern, path))


@dataclass
class FileInfo:
    """Information about a host file."""

    path: str
    size_bytes: int
    is_file: bool
    is_dir: bool
    exists: bool


class HostAdapter(ABC):
    """
    Abstract base class for host project access.

    All implementations must be READ-ONLY.
    Write operations are explicitly NOT supported in Sprint 5.
    """

    @abstractmethod
    def read_file(self, path: str) -> str:
        """
        Read file content from host.

        Args:
            path: Relative path from host root

        Returns:
            File content as string

        Raises:
            HostAccessDenied: If path is denied by policy
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def list_files(self, pattern: str = "*") -> List[str]:
        """
        List files matching pattern.

        Args:
            pattern: Glob pattern (e.g., "*.py", "src/**/*.js")

        Returns:
            List of matching file paths (relative to host root)

        Raises:
            HostAccessDenied: If pattern would access denied paths
        """
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """
        Check if file exists and is accessible.

        Args:
            path: Relative path from host root

        Returns:
            True if file exists and is allowed by policy
        """
        pass

    @abstractmethod
    def get_file_info(self, path: str) -> FileInfo:
        """
        Get file metadata.

        Args:
            path: Relative path from host root

        Returns:
            FileInfo with size, type, existence

        Raises:
            HostAccessDenied: If path is denied by policy
        """
        pass

    @abstractmethod
    def get_access_log(self) -> List[Dict[str, Any]]:
        """
        Get log of all file accesses.

        Returns:
            List of access records with path, timestamp, size
        """
        pass
