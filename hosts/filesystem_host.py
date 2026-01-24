"""
ProcessOS Filesystem Host Adapter

Read-only filesystem adapter with policy enforcement.
"""

import glob
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .host_interface import (
    FileInfo,
    HostAccessDenied,
    HostAdapter,
    HostPolicy,
)


class FilesystemHost(HostAdapter):
    """
    Filesystem-based host adapter with policy enforcement.

    Provides safe, read-only access to host project files.
    All access is logged for audit trail.
    """

    def __init__(
        self,
        root_path: Path,
        policy: Optional[HostPolicy] = None,
    ):
        """
        Initialize filesystem host adapter.

        Args:
            root_path: Root directory of the host project
            policy: Access policy (defaults to restrictive policy)
        """
        self.root_path = Path(root_path).resolve()
        self.policy = policy or HostPolicy.default()
        self._access_log: List[Dict[str, Any]] = []

    def _normalize_path(self, path: str) -> Path:
        """Normalize and resolve path relative to root."""
        # Convert to Path and make relative
        p = Path(path)

        # If absolute, make relative to root
        if p.is_absolute():
            try:
                p = p.relative_to(self.root_path)
            except ValueError:
                raise HostAccessDenied(
                    f"Path outside host root: {path}",
                    path=path,
                    reason="outside_root",
                )

        # Resolve the full path
        full_path = (self.root_path / p).resolve()

        # Security check: ensure path is still under root
        try:
            full_path.relative_to(self.root_path)
        except ValueError:
            raise HostAccessDenied(
                f"Path escapes host root: {path}",
                path=path,
                reason="path_escape",
            )

        return full_path

    def _get_relative_path(self, full_path: Path) -> str:
        """Get path relative to root as string."""
        return str(full_path.relative_to(self.root_path)).replace("\\", "/")

    def _check_policy(self, relative_path: str) -> None:
        """
        Check if path is allowed by policy.

        Args:
            relative_path: Path relative to root (forward slashes)

        Raises:
            HostAccessDenied: If path violates policy
        """
        # Always check denylist first
        if self.policy.matches_denylist(relative_path):
            raise HostAccessDenied(
                f"Path denied by policy: {relative_path}",
                path=relative_path,
                reason="denylist",
            )

        # Check allowlist if in allowlist mode
        if self.policy.mode == "allowlist":
            if not self.policy.matches_allowlist(relative_path):
                raise HostAccessDenied(
                    f"Path not in allowlist: {relative_path}",
                    path=relative_path,
                    reason="not_in_allowlist",
                )

    def _check_size(self, full_path: Path, relative_path: str) -> int:
        """
        Check if file size is within limits.

        Returns:
            File size in bytes

        Raises:
            HostAccessDenied: If file exceeds size limit
        """
        size = full_path.stat().st_size
        max_size = self.policy.limits.max_file_size_kb * 1024

        if size > max_size:
            raise HostAccessDenied(
                f"File too large: {size} bytes (max: {max_size})",
                path=relative_path,
                reason="size_exceeded",
            )

        return size

    def _log_access(
        self,
        path: str,
        operation: str,
        size_bytes: int = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Log file access for audit trail."""
        self._access_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": path,
                "operation": operation,
                "size_bytes": size_bytes,
                "success": success,
                "error": error,
            }
        )

    def read_file(self, path: str) -> str:
        """Read file content from host."""
        try:
            full_path = self._normalize_path(path)
            relative_path = self._get_relative_path(full_path)

            # Check policy
            self._check_policy(relative_path)

            # Check existence
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if not full_path.is_file():
                raise HostAccessDenied(
                    f"Not a file: {path}",
                    path=relative_path,
                    reason="not_a_file",
                )

            # Check size
            size = self._check_size(full_path, relative_path)

            # Read content
            content = full_path.read_text(encoding="utf-8")

            # Log success
            self._log_access(relative_path, "read", size_bytes=size)

            return content

        except HostAccessDenied:
            self._log_access(path, "read", success=False, error="access_denied")
            raise
        except FileNotFoundError:
            self._log_access(path, "read", success=False, error="not_found")
            raise
        except Exception as e:
            self._log_access(path, "read", success=False, error=str(e))
            raise

    def list_files(self, pattern: str = "*") -> List[str]:
        """List files matching pattern."""
        try:
            # Use glob to find matches
            search_pattern = str(self.root_path / pattern)
            matches = glob.glob(search_pattern, recursive=True)

            # Filter and validate each match
            results = []
            for match in matches:
                full_path = Path(match).resolve()

                # Skip directories
                if not full_path.is_file():
                    continue

                try:
                    relative_path = self._get_relative_path(full_path)
                    self._check_policy(relative_path)
                    results.append(relative_path)
                except HostAccessDenied:
                    # Skip denied files silently
                    continue

                # Enforce limit
                if len(results) >= self.policy.limits.max_files_per_query:
                    break

            # Log the query
            self._log_access(
                pattern, "list", size_bytes=len(results), success=True
            )

            return sorted(results)

        except Exception as e:
            self._log_access(pattern, "list", success=False, error=str(e))
            raise

    def file_exists(self, path: str) -> bool:
        """Check if file exists and is accessible."""
        try:
            full_path = self._normalize_path(path)
            relative_path = self._get_relative_path(full_path)

            # Check policy first
            self._check_policy(relative_path)

            # Check existence
            exists = full_path.exists() and full_path.is_file()

            self._log_access(relative_path, "exists", success=True)
            return exists

        except HostAccessDenied:
            # Denied paths are treated as non-existent
            return False
        except Exception:
            return False

    def get_file_info(self, path: str) -> FileInfo:
        """Get file metadata."""
        try:
            full_path = self._normalize_path(path)
            relative_path = self._get_relative_path(full_path)

            # Check policy
            self._check_policy(relative_path)

            exists = full_path.exists()

            if exists:
                stat = full_path.stat()
                info = FileInfo(
                    path=relative_path,
                    size_bytes=stat.st_size,
                    is_file=full_path.is_file(),
                    is_dir=full_path.is_dir(),
                    exists=True,
                )
            else:
                info = FileInfo(
                    path=relative_path,
                    size_bytes=0,
                    is_file=False,
                    is_dir=False,
                    exists=False,
                )

            self._log_access(relative_path, "info", success=True)
            return info

        except HostAccessDenied:
            self._log_access(path, "info", success=False, error="access_denied")
            raise

    def get_access_log(self) -> List[Dict[str, Any]]:
        """Get log of all file accesses."""
        return list(self._access_log)

    def clear_access_log(self) -> None:
        """Clear the access log."""
        self._access_log.clear()


class MockHostAdapter(HostAdapter):
    """
    In-memory mock host adapter for testing.

    Allows setting up fake file contents without touching filesystem.
    """

    def __init__(
        self,
        files: Optional[Dict[str, str]] = None,
        policy: Optional[HostPolicy] = None,
    ):
        """
        Initialize mock host adapter.

        Args:
            files: Dict mapping paths to content
            policy: Access policy (defaults to permissive)
        """
        self._files = files or {}
        self.policy = policy or HostPolicy(
            mode="denylist",
            denylist_patterns=[".git/**", ".env*"],
        )
        self._access_log: List[Dict[str, Any]] = []

    def add_file(self, path: str, content: str) -> None:
        """Add a file to the mock filesystem."""
        self._files[path.replace("\\", "/")] = content

    def _check_policy(self, path: str) -> None:
        """Check if path is allowed by policy."""
        normalized = path.replace("\\", "/")

        if self.policy.matches_denylist(normalized):
            raise HostAccessDenied(
                f"Path denied by policy: {path}",
                path=path,
                reason="denylist",
            )

        if self.policy.mode == "allowlist":
            if not self.policy.matches_allowlist(normalized):
                raise HostAccessDenied(
                    f"Path not in allowlist: {path}",
                    path=path,
                    reason="not_in_allowlist",
                )

    def _log_access(self, path: str, operation: str, **kwargs) -> None:
        """Log access."""
        self._access_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": path,
                "operation": operation,
                **kwargs,
            }
        )

    def read_file(self, path: str) -> str:
        """Read file content from mock."""
        normalized = path.replace("\\", "/")
        self._check_policy(normalized)

        if normalized not in self._files:
            raise FileNotFoundError(f"File not found: {path}")

        content = self._files[normalized]
        self._log_access(normalized, "read", size_bytes=len(content))
        return content

    def list_files(self, pattern: str = "*") -> List[str]:
        """List files matching pattern."""
        import fnmatch

        results = []
        for path in self._files.keys():
            if fnmatch.fnmatch(path, pattern):
                try:
                    self._check_policy(path)
                    results.append(path)
                except HostAccessDenied:
                    continue

        self._log_access(pattern, "list", count=len(results))
        return sorted(results)

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        normalized = path.replace("\\", "/")
        try:
            self._check_policy(normalized)
            return normalized in self._files
        except HostAccessDenied:
            return False

    def get_file_info(self, path: str) -> FileInfo:
        """Get file metadata."""
        normalized = path.replace("\\", "/")
        self._check_policy(normalized)

        if normalized in self._files:
            content = self._files[normalized]
            return FileInfo(
                path=normalized,
                size_bytes=len(content.encode("utf-8")),
                is_file=True,
                is_dir=False,
                exists=True,
            )
        else:
            return FileInfo(
                path=normalized,
                size_bytes=0,
                is_file=False,
                is_dir=False,
                exists=False,
            )

    def get_access_log(self) -> List[Dict[str, Any]]:
        """Get access log."""
        return list(self._access_log)
