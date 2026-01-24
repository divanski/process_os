"""
ProcessOS Host Adapter Layer

Provides safe, read-only access to host project files.
"""

from .host_interface import HostAdapter, HostAccessDenied, HostPolicy
from .filesystem_host import FilesystemHost, MockHostAdapter

__all__ = [
    "HostAdapter",
    "HostAccessDenied",
    "HostPolicy",
    "FilesystemHost",
    "MockHostAdapter",
]
