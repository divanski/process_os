"""
ProcessOS Telemetry Importer - JSONL to SQLite
Sprint 2: Import layer for migrating Sprint 1 telemetry events
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import jsonschema
import sqlite3
from datetime import datetime

from telemetry_store import TelemetryStore


def import_jsonl_to_sqlite(
    jsonl_path: str,
    db_path: str,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Import JSONL telemetry events to SQLite database.

    Args:
        jsonl_path: Path to JSONL file (one JSON object per line)
        db_path: Path to SQLite database
        overwrite: If False, append to existing DB (default: False)

    Returns:
        Dict with structure:
        {
            "success": bool,
            "imported": int,  # Number of successfully inserted events
            "skipped": int,   # Number of skipped duplicates
            "errors": []      # List of error messages
        }

    Raises:
        Exception: If >10% of events are invalid (data integrity concern)
    """

    # Initialize result dict
    result = {
        "success": False,
        "imported": 0,
        "skipped": 0,
        "errors": []
    }

    store = None
    try:
        # Initialize store
        store = TelemetryStore(db_path, create_tables=True)

        # Read JSONL file
        jsonl_file = Path(jsonl_path)
        if not jsonl_file.exists():
            result["errors"].append(f"JSONL file not found: {jsonl_path}")
            return result

        total_lines = 0
        error_count = 0

        # First pass: count total lines and validate
        with open(jsonl_file, 'r') as f:
            all_events = []
            for line_num, line in enumerate(f, start=1):
                total_lines += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse JSON
                    event = json.loads(line)
                    all_events.append((line_num, event))
                except json.JSONDecodeError as e:
                    error_msg = f"Malformed JSON (line {line_num}): {str(e)}"
                    result["errors"].append(error_msg)
                    sys.stderr.write(error_msg + "\n")
                    error_count += 1
                    continue

                # Validate against schema
                try:
                    jsonschema.validate(instance=event, schema=store._schema)
                except jsonschema.ValidationError as e:
                    error_msg = f"Invalid event (line {line_num}): {e.message}"
                    result["errors"].append(error_msg)
                    sys.stderr.write(error_msg + "\n")
                    error_count += 1
                    continue

        # Check error rate
        if total_lines > 0 and (error_count / total_lines) > 0.1:
            raise Exception(
                f"Too many validation errors: {error_count}/{total_lines} events invalid (>{10}%)"
            )

        # Start transaction
        store.conn.execute("BEGIN TRANSACTION")

        try:
            # Second pass: insert valid events
            for line_num, event in all_events:
                # Ensure run exists (create placeholder if orphaned)
                run_id = event.get("run_id")
                if run_id:
                    cursor = store.conn.execute(
                        "SELECT run_id FROM runs WHERE run_id = ?",
                        (run_id,)
                    )
                    if not cursor.fetchone():
                        # Create placeholder run
                        sys.stderr.write(
                            f"Creating orphaned run placeholder: {run_id}\n"
                        )
                        store.conn.execute(
                            """
                            INSERT INTO runs (run_id, playbook_id, status, started_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (run_id, "orphaned", "orphan", datetime.utcnow().isoformat() + "Z")
                        )

                # Check for missing step (if present)
                step_id = event.get("step_id")
                if step_id and run_id:
                    cursor = store.conn.execute(
                        "SELECT step_id FROM steps WHERE step_id = ? AND run_id = ?",
                        (step_id, run_id)
                    )
                    if not cursor.fetchone():
                        sys.stderr.write(
                            f"Warning: Step {step_id} not found in run {run_id}, "
                            "continuing anyway (non-strict mode)\n"
                        )

                # Extract fields
                event_id = event.get("event_id")
                agent_id = event.get("agent_id")
                event_type = event.get("event_type")
                criticality = event.get("criticality")
                timestamp = event.get("timestamp")
                data = event.get("data")

                # Insert event
                try:
                    store.conn.execute(
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
                    result["imported"] += 1
                except sqlite3.IntegrityError as e:
                    # Likely duplicate event_id
                    if "UNIQUE constraint failed" in str(e):
                        result["skipped"] += 1
                        sys.stderr.write(
                            f"Skipped duplicate event_id (line {line_num}): {event_id}\n"
                        )
                    else:
                        # Other FK error - handle non-strictly
                        if "FOREIGN KEY constraint failed" in str(e):
                            sys.stderr.write(
                                f"FK constraint warning (line {line_num}): {str(e)}, "
                                "attempting without step correlation\n"
                            )
                            # Try insert without step_id
                            try:
                                store.conn.execute(
                                    """
                                    INSERT INTO events (
                                        event_id, run_id, agent_id,
                                        event_type, criticality, timestamp, data
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        event_id,
                                        run_id,
                                        agent_id,
                                        event_type,
                                        criticality,
                                        timestamp,
                                        json.dumps(data) if data else None
                                    )
                                )
                                result["imported"] += 1
                            except Exception as e2:
                                error_msg = f"Error inserting event {event_id}: {str(e2)}"
                                result["errors"].append(error_msg)
                                sys.stderr.write(error_msg + "\n")
                        else:
                            error_msg = f"Error inserting event {event_id}: {str(e)}"
                            result["errors"].append(error_msg)
                            sys.stderr.write(error_msg + "\n")

            # Commit transaction
            store.conn.commit()
            result["success"] = True

        except Exception:
            # Rollback on any error
            store.conn.rollback()
            raise

    except Exception as e:
        result["success"] = False
        error_msg = f"Import failed: {str(e)}"
        result["errors"].append(error_msg)
        sys.stderr.write(error_msg + "\n")
        raise

    finally:
        # Always close store to prevent resource leaks
        if store is not None:
            store.close()

    return result
