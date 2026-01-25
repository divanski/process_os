"""
Append-only audit trail storage with JSON index.

Implements:
- T028: Append-only writer for audit entries
- T029: JSONL file format (.processos/audit/audit.jsonl)
- T031: JSON index for fast querying (.processos/audit/index.json)
- T032: Index update logic
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from process_os.audit.types import AuditEntry


class AuditStorageWriter:
    """
    Append-only writer for audit entries to JSONL file.

    Ensures entries are never overwritten, supporting audit trail integrity.
    Thread-safe for append operations on most filesystems.
    """

    def __init__(self, audit_dir: Path):
        """
        Initialize AuditStorageWriter.

        Args:
            audit_dir: Directory for audit files (.processos/audit)
        """
        self.audit_dir = Path(audit_dir)
        self.audit_file = self.audit_dir / "audit.jsonl"
        self.index_file = self.audit_dir / "index.json"

        # Ensure directory exists
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def append_entry(self, entry: AuditEntry) -> None:
        """
        Append audit entry to JSONL file.

        Append-only operation ensures no data loss or overwrites.
        Each entry is a complete JSON object on its own line.

        Args:
            entry: Audit entry to record
        """
        # Convert entry to JSON
        entry_json = json.dumps(entry.to_dict())

        # Append to file (creates if doesn't exist)
        with open(self.audit_file, "a") as f:
            f.write(entry_json + "\n")

    def append_entries(self, entries: List[AuditEntry]) -> None:
        """
        Append multiple audit entries in batch.

        Args:
            entries: List of audit entries to record
        """
        with open(self.audit_file, "a") as f:
            for entry in entries:
                entry_json = json.dumps(entry.to_dict())
                f.write(entry_json + "\n")

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Read all audit entries from JSONL file.

        Returns:
            List of entry dictionaries
        """
        if not self.audit_file.exists():
            return []

        entries = []
        with open(self.audit_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        pass

        return entries

    def get_entries_by_event_type(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Get all entries of a specific event type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching entries
        """
        entries = self.get_all_entries()
        return [e for e in entries if e.get("event_type") == event_type]

    def get_entries_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all entries created by a specific user.

        Args:
            user_id: User ID to filter by

        Returns:
            List of matching entries
        """
        entries = self.get_all_entries()
        return [e for e in entries if e.get("user_id") == user_id]

    def get_entry_count(self) -> int:
        """
        Get total number of entries in audit trail.

        Returns:
            Number of entries
        """
        if not self.audit_file.exists():
            return 0

        count = 0
        with open(self.audit_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    count += 1

        return count


class IndexManager:
    """
    Manages JSON index for fast querying of audit trail.

    Maintains:
    - Entry count
    - Indexed field values
    - File integrity hashes
    - Last indexed timestamp
    """

    def __init__(self, audit_dir: Path, storage_writer: AuditStorageWriter):
        """
        Initialize IndexManager.

        Args:
            audit_dir: Directory for audit files
            storage_writer: AuditStorageWriter instance for reading entries
        """
        self.audit_dir = Path(audit_dir)
        self.index_file = self.audit_dir / "index.json"
        self.audit_file = self.audit_dir / "audit.jsonl"
        self.storage_writer = storage_writer

    def build_index(self, project_id: str) -> Dict[str, Any]:
        """
        Build or rebuild index from audit file.

        Args:
            project_id: Project identifier

        Returns:
            Index dictionary
        """
        entries = self.storage_writer.get_all_entries()

        # Extract indexed fields
        event_types: Set[str] = set()
        user_ids: Set[str] = set()

        for entry in entries:
            if "event_type" in entry:
                event_types.add(entry["event_type"])
            if "user_id" in entry:
                user_ids.add(entry["user_id"])

        # Calculate file hash
        file_hash = self._get_file_hash(self.audit_file)

        # Build index
        index = {
            "project_id": project_id,
            "total_entries": len(entries),
            "indexed_fields": ["event_type", "user_id", "timestamp"],
            "indexed_event_types": sorted(list(event_types)),
            "indexed_user_ids": sorted(list(user_ids)),
            "last_indexed": datetime.now().isoformat(),
            "file_hashes": {"audit.jsonl": file_hash},
        }

        return index

    def update_index(self, project_id: str) -> None:
        """
        Update index after new entries added.

        Args:
            project_id: Project identifier
        """
        index = self.build_index(project_id)
        self._write_index(index)

    def get_index(self) -> Optional[Dict[str, Any]]:
        """
        Read current index from file.

        Returns:
            Index dictionary or None if not found
        """
        if not self.index_file.exists():
            return None

        try:
            with open(self.index_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def is_index_valid(self) -> bool:
        """
        Check if index matches current audit file state.

        Returns:
            True if index is current, False if needs rebuild
        """
        index = self.get_index()
        if index is None:
            return False

        # Check file hash
        stored_hash = index.get("file_hashes", {}).get("audit.jsonl")
        if not stored_hash:
            return False

        current_hash = self._get_file_hash(self.audit_file)
        if stored_hash != current_hash:
            return False

        # Check entry count
        current_count = self.storage_writer.get_entry_count()
        if index.get("total_entries", 0) != current_count:
            return False

        return True

    def get_entries_by_event_type(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Get entries of specific type using index-assisted filtering.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching entries
        """
        return self.storage_writer.get_entries_by_event_type(event_type)

    def get_entries_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get entries created by specific user using index-assisted filtering.

        Args:
            user_id: User ID to filter by

        Returns:
            List of matching entries
        """
        return self.storage_writer.get_entries_by_user(user_id)

    def get_index_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get summary of indexed information.

        Returns:
            Summary dict with counts and event types
        """
        index = self.get_index()
        if not index:
            return None

        return {
            "total_entries": index.get("total_entries", 0),
            "event_types": index.get("indexed_event_types", []),
            "user_count": len(index.get("indexed_user_ids", [])),
            "last_indexed": index.get("last_indexed"),
        }

    @staticmethod
    def _get_file_hash(file_path: Path) -> str:
        """
        Calculate SHA256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hex hash of file contents
        """
        if not file_path.exists():
            return ""

        hash_obj = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def _write_index(self, index: Dict[str, Any]) -> None:
        """
        Write index to JSON file.

        Args:
            index: Index dictionary to write
        """
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)


class AuditTrailManager:
    """
    High-level audit trail manager combining storage and indexing.

    Provides unified interface for recording and querying audit entries.
    """

    def __init__(self, audit_dir: Path, project_id: str):
        """
        Initialize AuditTrailManager.

        Args:
            audit_dir: Directory for audit files
            project_id: Project identifier
        """
        self.audit_dir = Path(audit_dir)
        self.project_id = project_id

        self.storage = AuditStorageWriter(self.audit_dir)
        self.index = IndexManager(self.audit_dir, self.storage)

        # Ensure index is up to date
        if not self.index.is_index_valid():
            self.index.update_index(self.project_id)

    def record_entry(self, entry: AuditEntry) -> None:
        """
        Record audit entry and update index.

        Args:
            entry: Audit entry to record
        """
        self.storage.append_entry(entry)
        # Update index after each entry (can batch later for performance)
        self.index.update_index(self.project_id)

    def record_entries(self, entries: List[AuditEntry]) -> None:
        """
        Record multiple audit entries and update index.

        Args:
            entries: List of entries to record
        """
        self.storage.append_entries(entries)
        # Update index after batch
        self.index.update_index(self.project_id)

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Get all audit entries.

        Returns:
            List of entries
        """
        return self.storage.get_all_entries()

    def query_by_event_type(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Query entries by event type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching entries
        """
        return self.index.get_entries_by_event_type(event_type)

    def query_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Query entries by user ID.

        Args:
            user_id: User ID to filter by

        Returns:
            List of matching entries
        """
        return self.index.get_entries_by_user(user_id)

    def get_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get audit trail summary.

        Returns:
            Summary information
        """
        return self.index.get_index_summary()

    def get_entry_count(self) -> int:
        """
        Get total number of entries.

        Returns:
            Entry count
        """
        return self.storage.get_entry_count()
