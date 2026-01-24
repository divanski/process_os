"""
ProcessOS CLI Module

Command-line interface for ProcessOS.
"""

import sys
from pathlib import Path

# Add grandparent directory to path for package imports when running from source
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from .errors import (
    CLIError,
    ErrorCode,
    ProcessOSError,
    format_error,
    format_error_by_code,
    get_error,
)
from .main import create_parser, main

__all__ = [
    "main",
    "create_parser",
    # Errors
    "CLIError",
    "ErrorCode",
    "ProcessOSError",
    "get_error",
    "format_error",
    "format_error_by_code",
]
