"""
ProcessOS Buffered Telemetry Writer

Sprint 2, Story S2-004: Engine Integration + Buffered Writer
Non-blocking, async telemetry persistence with critical event guarantees.
"""

import threading
import time
from typing import Dict, Any, Optional
from collections import deque

from telemetry_store import TelemetryStore


class BufferedTelemetryWriter:
    """
    Async buffered telemetry writer for non-blocking persistence.

    Features:
    - In-memory queue with configurable buffer size
    - Background writer thread flushes periodically or on batch threshold
    - Critical events always accepted (never dropped)
    - Non-critical events may be dropped under backpressure
    - Graceful shutdown with full flush
    """

    def __init__(
        self,
        store: TelemetryStore,
        buffer_size: int = 1000,
        flush_interval: float = 5.0,
        batch_size: int = 100
    ):
        """
        Initialize buffered writer.

        Args:
            store: TelemetryStore instance for persistence
            buffer_size: Max events in queue before backpressure
            flush_interval: Seconds between time-based flushes
            batch_size: Events to trigger batch flush
        """
        self.store = store
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.batch_size = batch_size

        # Thread-safe queue for events
        self._queue = deque(maxlen=None)  # No maxlen - we handle manually
        self._queue_lock = threading.Lock()

        # Counters
        self._dropped_count = 0
        self._dropped_lock = threading.Lock()

        # Control flags
        self._shutdown_event = threading.Event()
        self._flush_requested = threading.Event()

        # Start background writer thread
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="TelemetryWriter",
            daemon=True
        )
        self._writer_thread.start()

    @property
    def queue_size(self) -> int:
        """Current number of events in queue."""
        with self._queue_lock:
            return len(self._queue)

    @property
    def dropped_count(self) -> int:
        """Count of events dropped due to backpressure."""
        with self._dropped_lock:
            return self._dropped_count

    def put(self, event: Dict[str, Any]) -> bool:
        """
        Queue event for async persistence.

        Critical events are always accepted.
        Non-critical events may be dropped if queue is full.

        Args:
            event: Event dict to persist

        Returns:
            True if accepted, False if dropped
        """
        criticality = event.get("criticality", "normal")
        is_critical = criticality == "critical"

        with self._queue_lock:
            current_size = len(self._queue)

            # Critical events: always accept (may exceed buffer_size temporarily)
            if is_critical:
                self._queue.append(event)
                return True

            # Non-critical: check buffer capacity
            if current_size >= self.buffer_size:
                # Drop non-critical event
                with self._dropped_lock:
                    self._dropped_count += 1
                return False

            # Accept non-critical event
            self._queue.append(event)

            # Check if batch threshold reached
            if len(self._queue) >= self.batch_size:
                self._flush_requested.set()

            return True

    def flush(self) -> int:
        """
        Force immediate flush of all queued events.

        Returns:
            Number of events flushed
        """
        events_to_flush = []

        with self._queue_lock:
            while self._queue:
                events_to_flush.append(self._queue.popleft())

        flushed = 0
        for event in events_to_flush:
            try:
                self.store.persist_event(event)
                flushed += 1
            except Exception as e:
                # Log but don't halt
                print(f"[WARN] Failed to persist event: {e}")

        return flushed

    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Stop writer thread and flush remaining events.

        Args:
            timeout: Max seconds to wait for final flush
        """
        # Signal shutdown
        self._shutdown_event.set()
        self._flush_requested.set()  # Wake up writer thread

        # Wait for writer thread
        self._writer_thread.join(timeout=timeout)

        # Final flush (in case thread didn't complete)
        self.flush()

    def _writer_loop(self) -> None:
        """Background writer thread loop."""
        last_flush_time = time.time()

        while not self._shutdown_event.is_set():
            # Wait for flush trigger or timeout
            triggered = self._flush_requested.wait(timeout=min(1.0, self.flush_interval))

            if triggered:
                self._flush_requested.clear()

            # Check flush conditions
            current_time = time.time()
            time_since_flush = current_time - last_flush_time
            should_flush = False

            with self._queue_lock:
                queue_size = len(self._queue)

            # Flush if: interval elapsed, batch threshold, or shutdown
            if time_since_flush >= self.flush_interval and queue_size > 0:
                should_flush = True
            elif queue_size >= self.batch_size:
                should_flush = True
            elif self._shutdown_event.is_set() and queue_size > 0:
                should_flush = True

            if should_flush:
                self.flush()
                last_flush_time = time.time()

        # Final flush on shutdown
        self.flush()


# Global writer instance for engine integration
_global_writer: Optional[BufferedTelemetryWriter] = None
_global_writer_lock = threading.Lock()


def get_global_writer(
    db_path: Optional[str] = None,
    **kwargs
) -> Optional[BufferedTelemetryWriter]:
    """
    Get or create global BufferedTelemetryWriter instance.

    Args:
        db_path: Path to SQLite database (required on first call)
        **kwargs: Additional args for BufferedTelemetryWriter

    Returns:
        BufferedTelemetryWriter instance, or None if not configured
    """
    global _global_writer

    with _global_writer_lock:
        if _global_writer is None and db_path:
            store = TelemetryStore(db_path, create_tables=True)
            _global_writer = BufferedTelemetryWriter(store, **kwargs)
        return _global_writer


def shutdown_global_writer(timeout: float = 10.0) -> None:
    """Shutdown global writer instance."""
    global _global_writer

    with _global_writer_lock:
        if _global_writer is not None:
            _global_writer.shutdown(timeout=timeout)
            _global_writer = None
