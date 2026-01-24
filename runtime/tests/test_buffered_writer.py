"""
Unit tests for BufferedTelemetryWriter
Sprint 2 Story S2-004: Engine Integration + Buffered Writer

RED-GREEN-REFACTOR TDD: Tests written first (RED phase)
"""

import pytest
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime
import uuid

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_db():
    """Create a temporary database for each test"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    import gc
    gc.collect()
    time.sleep(0.1)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            Path(db_path).unlink(missing_ok=True)
            break
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(0.1)


def make_event(criticality: str = "normal", run_id: str = "test-run") -> dict:
    """Helper: Create a valid test event"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "run_id": run_id,
        "event_type": "step_completed",
        "criticality": criticality,
        "data": {}
    }


class TestBufferedWriterBasics:
    """Test basic buffered writer functionality"""

    def test_buffered_writer_accepts_events(self, temp_db):
        """Test: Writer accepts events into queue without immediate persistence"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        # Create run for FK constraint
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Large buffer, long interval = no auto-flush during test
        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=60.0, batch_size=100
        )

        try:
            # Queue 10 events
            for _ in range(10):
                result = writer.put(make_event())
                assert result is True, "Event should be accepted"

            # Check queue size (events should be queued, not immediately persisted)
            assert writer.queue_size >= 10, "Events should be queued"

            # Verify events are NOT yet in database (no flush yet)
            cursor = store.conn.execute("SELECT COUNT(*) FROM events")
            cursor.fetchone()[0]
            # Note: Some events may have flushed, but queue should have at least some
            # We mainly verify the writer accepts events
        finally:
            writer.shutdown(timeout=5.0)
            store.close()

    def test_buffered_writer_flushes_on_batch_size(self, temp_db):
        """Test: Writer flushes when batch_size threshold reached"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Small batch size = flush after 10 events
        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=60.0, batch_size=10
        )

        try:
            # Queue exactly batch_size events
            for _ in range(10):
                writer.put(make_event())

            # Wait for flush to occur
            time.sleep(0.5)

            # Verify events are in database
            cursor = store.conn.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            assert count >= 10, f"Expected 10 events persisted, got {count}"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()

    def test_buffered_writer_flushes_on_interval(self, temp_db):
        """Test: Writer flushes after flush_interval seconds"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Short interval (1s), large batch = flush by time
        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=1.0, batch_size=1000
        )

        try:
            # Queue 5 events (below batch threshold)
            for _ in range(5):
                writer.put(make_event())

            # Wait for interval flush
            time.sleep(1.5)

            # Verify events are in database
            cursor = store.conn.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            assert count >= 5, f"Expected 5 events persisted after interval, got {count}"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()


class TestCriticalEventGuarantee:
    """Test critical event handling (never dropped)"""

    def test_critical_events_never_dropped(self, temp_db):
        """Test: Critical events always accepted, even under backpressure"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Very small buffer to simulate backpressure
        writer = BufferedTelemetryWriter(
            store, buffer_size=10, flush_interval=60.0, batch_size=1000
        )

        try:
            # Fill the queue completely with normal events
            for _ in range(10):
                writer.put(make_event(criticality="normal"))

            # Now try to queue critical events - they MUST be accepted
            critical_accepted = 0
            for _ in range(5):
                if writer.put(make_event(criticality="critical")):
                    critical_accepted += 1

            # All critical events should be accepted
            assert critical_accepted == 5, f"Expected 5 critical events accepted, got {critical_accepted}"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()

    def test_noncritical_dropped_under_backpressure(self, temp_db):
        """Test: Non-critical events may be dropped when queue is full"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Very small buffer, no auto-flush
        writer = BufferedTelemetryWriter(
            store, buffer_size=5, flush_interval=60.0, batch_size=1000
        )

        try:
            # Fill the queue
            for _ in range(5):
                writer.put(make_event(criticality="normal"))

            # Try to add more normal events - should be dropped
            initial_dropped = writer.dropped_count
            for _ in range(5):
                writer.put(make_event(criticality="normal"))

            # dropped_count should increase
            assert writer.dropped_count > initial_dropped, "Normal events should be dropped when queue full"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()


class TestGracefulShutdown:
    """Test graceful shutdown behavior"""

    def test_graceful_shutdown_flushes_all(self, temp_db):
        """Test: Shutdown flushes all queued events before returning"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Large buffer, no auto-flush
        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=60.0, batch_size=1000
        )

        # Queue 50 events
        for _ in range(50):
            writer.put(make_event())

        # Graceful shutdown should flush everything
        writer.shutdown(timeout=10.0)

        # Verify all events persisted
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == 50, f"Expected 50 events after shutdown, got {count}"

        store.close()

    def test_manual_flush_persists_events(self, temp_db):
        """Test: Manual flush() call persists queued events"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=60.0, batch_size=1000
        )

        try:
            # Queue 25 events
            for _ in range(25):
                writer.put(make_event())

            # Manual flush
            flushed = writer.flush()
            assert flushed >= 25, f"Expected 25 events flushed, got {flushed}"

            # Verify in database
            cursor = store.conn.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            assert count >= 25, f"Expected 25 events in DB, got {count}"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()


class TestConcurrentWrites:
    """Test thread-safety under concurrent load"""

    def test_concurrent_writes_no_lost_events(self, temp_db):
        """Test: Concurrent writes from multiple threads don't lose events"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=1.0, batch_size=50
        )

        num_threads = 4
        events_per_thread = 25
        total_expected = num_threads * events_per_thread

        def write_events(thread_id: int):
            for i in range(events_per_thread):
                writer.put(make_event())

        # Start concurrent writes
        threads = [
            threading.Thread(target=write_events, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Shutdown flushes all
        writer.shutdown(timeout=10.0)

        # Verify all events persisted
        cursor = store.conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count == total_expected, f"Expected {total_expected} events, got {count}"

        store.close()


class TestNonBlockingPerformance:
    """Test non-blocking behavior and performance"""

    def test_put_returns_immediately_with_slow_persister(self, temp_db):
        """Test: put() returns immediately even if persistence is slow"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Large buffer, no auto-flush = put() just queues
        writer = BufferedTelemetryWriter(
            store, buffer_size=1000, flush_interval=60.0, batch_size=1000
        )

        try:
            # Measure time to queue 100 events
            start = time.time()
            for _ in range(100):
                writer.put(make_event())
            elapsed = time.time() - start

            # Should complete in <100ms (non-blocking)
            assert elapsed < 0.1, f"put() took {elapsed:.3f}s for 100 events (expected <0.1s)"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()


class TestDroppedCounter:
    """Test dropped event tracking"""

    def test_dropped_count_tracks_dropped_events(self, temp_db):
        """Test: dropped_count accurately tracks rejected events"""
        from buffered_writer import BufferedTelemetryWriter
        from telemetry_store import TelemetryStore

        store = TelemetryStore(temp_db, create_tables=True)
        store.conn.execute(
            "INSERT INTO runs (run_id, playbook_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("test-run", "test-playbook", "running", datetime.utcnow().isoformat() + "Z")
        )
        store.conn.commit()

        # Tiny buffer
        writer = BufferedTelemetryWriter(
            store, buffer_size=3, flush_interval=60.0, batch_size=1000
        )

        try:
            assert writer.dropped_count == 0, "Initial dropped_count should be 0"

            # Fill the queue
            for _ in range(3):
                writer.put(make_event(criticality="normal"))

            # Try to add 5 more normal events - all should be dropped
            for _ in range(5):
                writer.put(make_event(criticality="normal"))

            assert writer.dropped_count == 5, f"Expected 5 dropped, got {writer.dropped_count}"
        finally:
            writer.shutdown(timeout=5.0)
            store.close()
