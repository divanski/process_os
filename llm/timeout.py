"""
Timeout and operation cancellation mechanism for large project analysis.

Prevents long-running operations from blocking the UI indefinitely.
Supports configurable timeouts with graceful cancellation.
"""

import time
from typing import Optional, Callable
from datetime import datetime


class OperationTimeout:
    """
    Manages timeout for long-running analysis operations.

    Default timeout: 300 seconds (5 minutes)
    Configurable per operation
    """

    DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes
    MIN_TIMEOUT = 60  # 1 minute minimum
    MAX_TIMEOUT = 3600  # 1 hour maximum

    def __init__(self, operation_id: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        """
        Initialize operation timeout.

        Args:
            operation_id: Unique operation ID
            timeout_seconds: Timeout in seconds (will be clamped to valid range)
        """
        self.operation_id = operation_id

        # Clamp timeout to valid range
        self.timeout_seconds = max(
            self.MIN_TIMEOUT, min(timeout_seconds, self.MAX_TIMEOUT)
        )

        # Timing tracking
        self.start_time: Optional[float] = None
        self.paused_time: Optional[float] = None
        self.total_paused_seconds = 0.0

        # Callback for timeout
        self.timeout_callback: Optional[Callable[[], None]] = None

    def start(self):
        """Start the timeout clock."""
        if self.start_time is None:
            self.start_time = time.time()

    def pause(self):
        """Pause the timeout clock."""
        if self.paused_time is None and self.start_time is not None:
            self.paused_time = time.time()

    def resume(self):
        """Resume the timeout clock."""
        if self.paused_time is not None:
            pause_duration = time.time() - self.paused_time
            self.total_paused_seconds += pause_duration
            self.paused_time = None

    def is_expired(self) -> bool:
        """
        Check if timeout has expired.

        Returns:
            True if operation has exceeded timeout
        """
        if self.start_time is None:
            return False

        elapsed = self.get_elapsed_seconds()
        return elapsed >= self.timeout_seconds

    def get_elapsed_seconds(self) -> float:
        """
        Get elapsed time excluding paused periods.

        Returns:
            Elapsed seconds
        """
        if self.start_time is None:
            return 0.0

        current_time = time.time()
        total_elapsed = current_time - self.start_time

        # Subtract paused time if currently paused
        if self.paused_time is not None:
            total_elapsed -= (current_time - self.paused_time)

        # Subtract previously paused time
        total_elapsed -= self.total_paused_seconds

        return max(0.0, total_elapsed)

    def get_remaining_seconds(self) -> float:
        """
        Get remaining time before timeout.

        Returns:
            Remaining seconds (0 if already expired)
        """
        elapsed = self.get_elapsed_seconds()
        remaining = self.timeout_seconds - elapsed
        return max(0.0, remaining)

    def get_progress_percent(self) -> float:
        """
        Get timeout progress as percentage.

        Returns:
            Percentage of timeout used (0-100)
        """
        elapsed = self.get_elapsed_seconds()
        return (elapsed / self.timeout_seconds * 100) if self.timeout_seconds > 0 else 0

    def check_and_invoke_timeout(self) -> bool:
        """
        Check if expired and invoke callback if so.

        Returns:
            True if timeout was triggered
        """
        if self.is_expired():
            if self.timeout_callback:
                self.timeout_callback()
            return True

        return False


class CancellableOperation:
    """
    Wraps an operation with cancellation and timeout support.

    Tracks cancellation state and timeout.
    """

    def __init__(
        self,
        operation_id: str,
        timeout_seconds: Optional[int] = None,
    ):
        """
        Initialize cancellable operation.

        Args:
            operation_id: Unique operation ID
            timeout_seconds: Optional timeout in seconds
        """
        self.operation_id = operation_id
        self.is_cancelled = False
        self.cancel_reason: Optional[str] = None
        self.cancelled_at: Optional[str] = None

        # Timeout management
        self.timeout = OperationTimeout(
            operation_id,
            timeout_seconds or OperationTimeout.DEFAULT_TIMEOUT_SECONDS,
        )

        # Cancellation callbacks
        self.cancel_callbacks = []

    def start(self):
        """Start the operation (begins timeout)."""
        self.timeout.start()

    def cancel(self, reason: Optional[str] = None) -> bool:
        """
        Cancel the operation.

        Args:
            reason: Optional reason for cancellation

        Returns:
            True if cancelled successfully
        """
        if self.is_cancelled:
            return False

        self.is_cancelled = True
        self.cancel_reason = reason or "User cancelled"
        self.cancelled_at = datetime.utcnow().isoformat() + "Z"

        # Invoke callbacks
        for callback in self.cancel_callbacks:
            callback(self.cancel_reason)

        return True

    def register_cancel_callback(self, callback: Callable[[str], None]):
        """
        Register callback for cancellation.

        Args:
            callback: Function called on cancellation
        """
        self.cancel_callbacks.append(callback)

    def check_timeout(self) -> bool:
        """
        Check if timeout has expired.

        Returns:
            True if timeout expired
        """
        if self.timeout.is_expired():
            self.cancel(reason="Operation timeout")
            return True

        return False

    def should_continue(self) -> bool:
        """
        Check if operation should continue.

        Returns:
            False if cancelled or timed out
        """
        if self.is_cancelled:
            return False

        return not self.check_timeout()

    def get_status(self) -> Dict[str, Any]:
        """
        Get current operation status.

        Returns:
            Status dictionary
        """
        return {
            "operation_id": self.operation_id,
            "is_cancelled": self.is_cancelled,
            "cancel_reason": self.cancel_reason,
            "cancelled_at": self.cancelled_at,
            "elapsed_seconds": self.timeout.get_elapsed_seconds(),
            "remaining_seconds": self.timeout.get_remaining_seconds(),
            "timeout_progress_percent": self.timeout.get_progress_percent(),
        }


class TimeoutMessage:
    """Message sent when operation times out."""

    def __init__(self, operation_id: str, elapsed_seconds: float):
        """
        Initialize timeout message.

        Args:
            operation_id: ID of timed-out operation
            elapsed_seconds: Time elapsed before timeout
        """
        self.operation_id = operation_id
        self.message_type = "OPERATION_TIMEOUT"
        self.elapsed_seconds = elapsed_seconds
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.reason = f"Operation exceeded {OperationTimeout.DEFAULT_TIMEOUT_SECONDS}s timeout"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.message_type,
            "operation_id": self.operation_id,
            "elapsed_seconds": self.elapsed_seconds,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


class CancellationMessage:
    """Message sent when operation is cancelled."""

    def __init__(self, operation_id: str, reason: str):
        """
        Initialize cancellation message.

        Args:
            operation_id: ID of cancelled operation
            reason: Reason for cancellation
        """
        self.operation_id = operation_id
        self.message_type = "OPERATION_CANCELLED"
        self.reason = reason
        self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.message_type,
            "operation_id": self.operation_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# Type hints
from typing import Dict, Any
