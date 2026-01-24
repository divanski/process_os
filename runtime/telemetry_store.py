"""
ProcessOS Telemetry Store - SQLite Persistence Layer

Sprint 2: Layer 3 Telemetry Persistence
Provides non-blocking persistence of telemetry events with schema validation.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import jsonschema


class TelemetryStore:
    """
    SQLite-backed telemetry persistence layer.
    Thread-safe, non-blocking event persistence with schema validation.
    """

    def __init__(self, db_path: str, create_tables: bool = True, schema_path: Optional[str] = None):
        """
        Initialize TelemetryStore and create database tables if needed.

        Args:
            db_path: Path to SQLite database file
            create_tables: If True, execute DDL to create tables
            schema_path: Path to telemetry.event.schema.json for validation
        """
        self.db_path = db_path
        self.schema_path = schema_path or (
            Path(__file__).parent.parent / "schemas" / "telemetry.event.schema.json"
        )
        self._lock = threading.Lock()

        # Open connection with threading support
        self.conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            timeout=10.0  # 10s timeout for locks
        )
        self.conn.row_factory = sqlite3.Row

        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

        if create_tables:
            self._create_tables()

        # Load schema for validation
        self._schema = self._load_event_schema()

    def _create_tables(self) -> None:
        """Execute DDL to create tables from schema.sql"""
        schema_file = Path(__file__).parent.parent / "schemas" / "telemetry.db.schema.sql"

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_file, "r") as f:
            ddl = f.read()

        with self._lock:
            self.conn.executescript(ddl)
            self.conn.commit()

    def _load_event_schema(self) -> Dict[str, Any]:
        """Load telemetry.event.schema.json for validation"""
        if not self.schema_path.exists() if isinstance(self.schema_path, Path) else not Path(self.schema_path).exists():
            raise FileNotFoundError(f"Event schema not found: {self.schema_path}")

        with open(self.schema_path, "r") as f:
            return json.load(f)

    def persist_event(self, event: Dict[str, Any]) -> None:
        """
        Persist a telemetry event to SQLite after schema validation.
        Thread-safe. Non-blocking (returns immediately).

        Args:
            event: Event dictionary conforming to telemetry.event.schema.json

        Raises:
            ValueError: If event fails schema validation
            sqlite3.Error: If database write fails
        """
        # Validate against schema
        try:
            jsonschema.validate(instance=event, schema=self._schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Event validation failed: {e.message}") from e

        # Extract fields (with NULL handling)
        event_id = event.get("event_id")
        run_id = event.get("run_id")
        step_id = event.get("step_id")
        agent_id = event.get("agent_id")
        event_type = event.get("event_type")
        criticality = event.get("criticality")
        timestamp = event.get("timestamp")
        data = event.get("data")

        if not all([event_id, run_id, event_type, criticality, timestamp]):
            raise ValueError("Event missing required fields: event_id, run_id, event_type, criticality, timestamp")

        # Insert to events table
        with self._lock:
            try:
                self.conn.execute(
                    """
                    INSERT INTO events (
                        event_id, run_id, step_id, agent_id,
                        event_type, criticality, timestamp, data
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        run_id,
                        step_id,
                        agent_id,
                        event_type,
                        criticality,
                        timestamp,
                        json.dumps(data) if data else None
                    )
                )
                self.conn.commit()
            except sqlite3.IntegrityError as e:
                self.conn.rollback()
                raise ValueError(f"Database integrity error: {str(e)}") from e
            except sqlite3.Error:
                self.conn.rollback()
                raise

    # =========================================================================
    # Query Methods (S2-003)
    # =========================================================================

    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information for a specific run.

        Args:
            run_id: The run identifier

        Returns:
            Dict with run summary or None if run not found:
            {
                "run_id": str,
                "playbook_id": str,
                "status": str,
                "steps_count": int,
                "events_count": int,
                "artifacts_count": int,
                "started_at": str (ISO timestamp),
                "ended_at": str or None
            }
        """
        with self._lock:
            # Get run metadata
            cursor = self.conn.execute(
                "SELECT run_id, playbook_id, status, started_at, ended_at FROM runs WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            # Count steps
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM steps WHERE run_id = ?",
                (run_id,)
            )
            steps_count = cursor.fetchone()[0]

            # Count events
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM events WHERE run_id = ?",
                (run_id,)
            )
            events_count = cursor.fetchone()[0]

            # Count artifacts
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM artifacts WHERE run_id = ?",
                (run_id,)
            )
            artifacts_count = cursor.fetchone()[0]

            return {
                "run_id": row["run_id"],
                "playbook_id": row["playbook_id"],
                "status": row["status"],
                "steps_count": steps_count,
                "events_count": events_count,
                "artifacts_count": artifacts_count,
                "started_at": row["started_at"],
                "ended_at": row["ended_at"]
            }

    def get_step_timeline(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ordered step timeline with gate results for a run.

        Args:
            run_id: The run identifier

        Returns:
            Dict with step timeline or None if run not found:
            {
                "run_id": str,
                "steps": [
                    {
                        "step_id": str,
                        "agent_id": str or None,
                        "status": str,
                        "started_at": str,
                        "ended_at": str or None,
                        "gate_results": [
                            {"gate_name": str, "result": bool, "reason": str}
                        ],
                        "artifact_ids": [str]
                    }
                ]
            }
        """
        with self._lock:
            # Check if run exists
            cursor = self.conn.execute(
                "SELECT run_id FROM runs WHERE run_id = ?",
                (run_id,)
            )
            if cursor.fetchone() is None:
                return None

            # Get steps ordered by started_at
            cursor = self.conn.execute(
                """
                SELECT step_id, agent_id, status, started_at, ended_at
                FROM steps
                WHERE run_id = ?
                ORDER BY started_at ASC
                """,
                (run_id,)
            )
            steps = cursor.fetchall()

            result_steps = []
            for step in steps:
                step_id = step["step_id"]

                # Get gate events for this step
                cursor = self.conn.execute(
                    """
                    SELECT data
                    FROM events
                    WHERE run_id = ? AND step_id = ? AND event_type IN ('gate_passed', 'gate_failed')
                    ORDER BY timestamp ASC
                    """,
                    (run_id, step_id)
                )
                gate_events = cursor.fetchall()

                gate_results = []
                for gate_event in gate_events:
                    if gate_event["data"]:
                        data = json.loads(gate_event["data"])
                        gate_results.append({
                            "gate_name": data.get("gate_name", "unknown"),
                            "result": data.get("gate_result", False),
                            "reason": data.get("gate_reason", "")
                        })

                # Get artifact IDs for this step
                cursor = self.conn.execute(
                    """
                    SELECT artifact_id
                    FROM artifacts
                    WHERE run_id = ? AND created_by_step = ?
                    """,
                    (run_id, step_id)
                )
                artifact_ids = [row["artifact_id"] for row in cursor.fetchall()]

                result_steps.append({
                    "step_id": step_id,
                    "agent_id": step["agent_id"],
                    "status": step["status"],
                    "started_at": step["started_at"],
                    "ended_at": step["ended_at"],
                    "gate_results": gate_results,
                    "artifact_ids": artifact_ids
                })

            return {
                "run_id": run_id,
                "steps": result_steps
            }

    def list_failed_runs(self, limit: int = 20) -> Dict[str, Any]:
        """
        List failed runs with failure reason, ordered by end time descending.

        Args:
            limit: Maximum number of runs to return (default 20)

        Returns:
            Dict with failed runs list:
            {
                "runs": [
                    {
                        "run_id": str,
                        "playbook_id": str,
                        "failed_step": str or None,
                        "reason": str,
                        "ended_at": str
                    }
                ]
            }
        """
        with self._lock:
            # Get failed runs ordered by ended_at DESC
            cursor = self.conn.execute(
                """
                SELECT run_id, playbook_id, ended_at
                FROM runs
                WHERE status = 'failed'
                ORDER BY ended_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            failed_runs = cursor.fetchall()

            result_runs = []
            for run in failed_runs:
                run_id = run["run_id"]

                # Find first error event for this run to get reason
                cursor = self.conn.execute(
                    """
                    SELECT step_id, data
                    FROM events
                    WHERE run_id = ? AND event_type = 'error'
                    ORDER BY timestamp ASC
                    LIMIT 1
                    """,
                    (run_id,)
                )
                error_event = cursor.fetchone()

                reason = "Unknown error"
                failed_step = None
                if error_event:
                    failed_step = error_event["step_id"]
                    if error_event["data"]:
                        data = json.loads(error_event["data"])
                        reason = data.get("error_message", "Unknown error")

                result_runs.append({
                    "run_id": run_id,
                    "playbook_id": run["playbook_id"],
                    "failed_step": failed_step,
                    "reason": reason,
                    "ended_at": run["ended_at"]
                })

            return {"runs": result_runs}

    def close(self) -> None:
        """Close database connection gracefully"""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.close()
        except Exception:
            pass
