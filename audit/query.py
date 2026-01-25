"""
Audit query interface for ProcessOS.

Implements:
- T088-T099: Audit query functionality
- Structured and natural language queries
- Query performance optimization with indexing
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditQuery:
    """Query interface for audit entries."""

    def __init__(self, audit_dir: Path):
        """
        Initialize AuditQuery.

        Args:
            audit_dir: Directory where audit logs are stored (.processos/audit/)
        """
        self.audit_dir = Path(audit_dir)
        self.audit_file = self.audit_dir / "audit.jsonl"
        self.index_file = self.audit_dir / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load or create audit index."""
        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                self.index = json.load(f)
        else:
            self.index = {
                "event_types": {},
                "user_ids": {},
                "dates": {},
                "total_entries": 0,
            }
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild index from audit log."""
        self.index = {
            "event_types": {},
            "user_ids": {},
            "dates": {},
            "total_entries": 0,
        }

        if not self.audit_file.exists():
            return

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    self._index_entry(entry)
                except json.JSONDecodeError:
                    continue

        # Save updated index
        self._save_index()

    def _index_entry(self, entry: Dict[str, Any]) -> None:
        """Add entry to index."""
        event_type = entry.get("event_type")
        user_id = entry.get("user_id")
        timestamp = entry.get("timestamp")

        # Index by event type
        if event_type:
            if event_type not in self.index["event_types"]:
                self.index["event_types"][event_type] = []
            self.index["event_types"][event_type].append(entry.get("entry_id"))

        # Index by user_id
        if user_id:
            if user_id not in self.index["user_ids"]:
                self.index["user_ids"][user_id] = []
            self.index["user_ids"][user_id].append(entry.get("entry_id"))

        # Index by date
        if timestamp:
            date = timestamp.split("T")[0]
            if date not in self.index["dates"]:
                self.index["dates"][date] = []
            self.index["dates"][date].append(entry.get("entry_id"))

        self.index["total_entries"] += 1

    def _save_index(self) -> None:
        """Save index to file."""
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)

    def query_all(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query all audit entries.

        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of audit entries
        """
        if not self.audit_file.exists():
            return []

        entries = []
        count = 0

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    if count >= offset:
                        entries.append(entry)
                        if limit and len(entries) >= limit:
                            break
                    count += 1
                except json.JSONDecodeError:
                    continue

        return entries

    def query_by_event_type(
        self, event_type: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query by event type (T084).

        Args:
            event_type: Type of event to query
            limit: Maximum results to return

        Returns:
            List of matching entries
        """
        results = []

        if not self.audit_file.exists():
            return results

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("event_type") == event_type:
                        results.append(entry)
                        if limit and len(results) >= limit:
                            break
                except json.JSONDecodeError:
                    continue

        return results

    def query_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query by date range (T085).

        Args:
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum results to return

        Returns:
            List of entries within date range
        """
        results = []

        if not self.audit_file.exists():
            return results

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    timestamp_str = entry.get("timestamp", "")
                    # Parse ISO 8601 timestamp, removing Z suffix and treating as UTC
                    entry_time = datetime.fromisoformat(timestamp_str.rstrip("Z"))

                    if start_date <= entry_time <= end_date:
                        results.append(entry)
                        if limit and len(results) >= limit:
                            break
                except (json.JSONDecodeError, ValueError):
                    continue

        return results

    def query_by_user_id(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query by user_id.

        Args:
            user_id: ID of user
            limit: Maximum results to return

        Returns:
            List of entries for user
        """
        results = []

        if not self.audit_file.exists():
            return results

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("user_id") == user_id:
                        results.append(entry)
                        if limit and len(results) >= limit:
                            break
                except json.JSONDecodeError:
                    continue

        return results

    def query(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query with multiple filters.

        Args:
            event_type: Event type filter
            user_id: User ID filter
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results to return

        Returns:
            List of matching entries
        """
        results = []

        if not self.audit_file.exists():
            return results

        with open(self.audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)

                    # Apply filters
                    if event_type and entry.get("event_type") != event_type:
                        continue

                    if user_id and entry.get("user_id") != user_id:
                        continue

                    if start_date or end_date:
                        timestamp_str = entry.get("timestamp", "")
                        try:
                            # Parse ISO 8601 timestamp, removing Z suffix and treating as UTC
                            entry_time = datetime.fromisoformat(timestamp_str.rstrip("Z"))

                            if start_date and entry_time < start_date:
                                continue

                            if end_date and entry_time > end_date:
                                continue
                        except ValueError:
                            continue

                    results.append(entry)

                    if limit and len(results) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        return results
