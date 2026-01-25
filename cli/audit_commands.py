"""
CLI commands for audit trail access.

Implements:
- T098-T099: Audit query CLI commands
- Query audit trail from command line
- Multiple query formats (structured, date range, user-based)
- Formatted output for terminal display
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from process_os.audit.query import AuditQuery


class AuditFormatter:
    """Formats audit entries for terminal display."""

    @staticmethod
    def format_entry(entry: dict) -> str:
        """
        Format audit entry for display.

        Args:
            entry: Audit entry dictionary

        Returns:
            Formatted string for display
        """
        lines = []

        # Header
        timestamp = entry.get("timestamp", "N/A")
        event_type = entry.get("event_type", "unknown")
        user_id = entry.get("user_id", "unknown")

        lines.append(f"[{timestamp}] {event_type} (user: {user_id})")
        lines.append("-" * 60)

        # Metadata
        metadata = entry.get("metadata", {})
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                lines.append(f"  {key}:")
                lines.append(f"    {json.dumps(value, indent=2)}")
            else:
                lines.append(f"  {key}: {value}")

        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_summary(entries: list) -> str:
        """
        Format multiple entries as summary.

        Args:
            entries: List of audit entries

        Returns:
            Formatted summary string
        """
        lines = []

        lines.append(f"Found {len(entries)} audit entries")
        lines.append("-" * 60)

        # Count by event type
        event_counts = {}
        for entry in entries:
            event_type = entry.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        if event_counts:
            lines.append("Events by type:")
            for event_type, count in sorted(event_counts.items()):
                lines.append(f"  {event_type}: {count}")

        # Date range
        if entries:
            timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
            if timestamps:
                timestamps.sort()
                lines.append(f"\nDate range: {timestamps[0]} to {timestamps[-1]}")

        lines.append("")

        return "\n".join(lines)


def audit_query_command(
    audit_dir: Optional[Path] = None,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    output_format: str = "text",
    limit: Optional[int] = None,
) -> None:
    """
    Query audit trail (T098).

    Args:
        audit_dir: Audit directory (.processos/audit/)
        event_type: Filter by event type
        user_id: Filter by user ID
        date_from: Filter from date (YYYY-MM-DD)
        date_to: Filter to date (YYYY-MM-DD)
        output_format: Output format ('text' or 'json')
        limit: Maximum results to return
    """
    # Determine audit directory
    if audit_dir is None:
        audit_dir = Path(".processos") / "audit"

    if not audit_dir.exists():
        print(f"[ERROR] Audit directory not found: {audit_dir}")
        return

    # Initialize query interface
    query_interface = AuditQuery(audit_dir)

    # Parse date filters
    start_date = None
    end_date = None

    if date_from:
        try:
            start_date = datetime.fromisoformat(date_from)
        except ValueError:
            print(f"[ERROR] Invalid date format for --from: {date_from}")
            return

    if date_to:
        try:
            end_date = datetime.fromisoformat(date_to)
        except ValueError:
            print(f"[ERROR] Invalid date format for --to: {date_to}")
            return

    # Execute query
    results = query_interface.query(
        event_type=event_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    # Format output
    if output_format == "json":
        print(json.dumps(results, indent=2))
    else:
        # Text format
        print(AuditFormatter.format_summary(results))
        print("\nEntries:")
        print("=" * 60)

        for entry in results:
            print(AuditFormatter.format_entry(entry))


def audit_list_command(
    audit_dir: Optional[Path] = None,
    limit: int = 50,
    offset: int = 0,
) -> None:
    """
    List audit entries (T099).

    Args:
        audit_dir: Audit directory (.processos/audit/)
        limit: Maximum results per page
        offset: Starting offset
    """
    # Determine audit directory
    if audit_dir is None:
        audit_dir = Path(".processos") / "audit"

    if not audit_dir.exists():
        print(f"[ERROR] Audit directory not found: {audit_dir}")
        return

    # Initialize query interface
    query_interface = AuditQuery(audit_dir)

    # Get all entries
    results = query_interface.query_all(limit=limit, offset=offset)

    # Display summary
    print(AuditFormatter.format_summary(results))

    if results:
        print(f"\nShowing {len(results)} of {query_interface.index.get('total_entries', 0)} entries")
        print("(Use --offset to paginate)")
        print("=" * 60)

        for entry in results:
            print(AuditFormatter.format_entry(entry))


def audit_export_command(
    audit_dir: Optional[Path] = None,
    output_file: Optional[Path] = None,
    format: str = "json",
) -> None:
    """
    Export audit trail (T099).

    Args:
        audit_dir: Audit directory (.processos/audit/)
        output_file: Output file path
        format: Export format ('json' or 'csv')
    """
    # Determine audit directory
    if audit_dir is None:
        audit_dir = Path(".processos") / "audit"

    if not audit_dir.exists():
        print(f"[ERROR] Audit directory not found: {audit_dir}")
        return

    # Initialize query interface
    query_interface = AuditQuery(audit_dir)

    # Get all entries
    results = query_interface.query_all()

    # Determine output file
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"audit_export_{timestamp}.{format}")

    # Export
    try:
        if format == "json":
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
        elif format == "csv":
            import csv

            # Flatten entries for CSV
            flat_entries = []
            for entry in results:
                flat = {
                    "timestamp": entry.get("timestamp"),
                    "event_type": entry.get("event_type"),
                    "user_id": entry.get("user_id"),
                    "session_id": entry.get("session_id"),
                }
                # Add metadata fields
                metadata = entry.get("metadata", {})
                for key, value in metadata.items():
                    if isinstance(value, (list, dict)):
                        flat[f"metadata_{key}"] = json.dumps(value)
                    else:
                        flat[f"metadata_{key}"] = value

                flat_entries.append(flat)

            # Write CSV
            if flat_entries:
                fieldnames = flat_entries[0].keys()
                with open(output_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(flat_entries)
        else:
            print(f"[ERROR] Unsupported format: {format}")
            return

        print(f"[OK] Exported {len(results)} entries to {output_file}")

    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
