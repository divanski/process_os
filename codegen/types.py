"""
ProcessOS Code Generation Types Module

Data models for generated code artifacts and patchsets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReviewStatus(Enum):
    """Status of code review."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class FileType(Enum):
    """Types of generated files."""

    MODEL = "model"
    SERVICE = "service"
    CONTROLLER = "controller"
    ROUTE = "route"
    TEST = "test"
    CONFIG = "config"
    MIGRATION = "migration"
    DOCUMENTATION = "documentation"


class FileDecision(Enum):
    """User decision on a generated file."""

    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass
class GeneratedFile:
    """A single generated file."""

    id: str
    file_path: Path  # Relative path where file will be created
    file_type: FileType

    # Content
    content: str  # Full file content

    # For modifications to existing files
    is_modification: bool = False
    original_content: Optional[str] = None  # If modifying existing file
    diff: Optional[str] = None  # Unified diff format

    # Review status (per-file)
    user_decision: Optional[FileDecision] = None
    modified_content: Optional[str] = None  # If user modified

    @property
    def final_content(self) -> str:
        """Get the final content to apply (user-modified if available)."""
        if self.modified_content is not None:
            return self.modified_content
        return self.content

    def accept(self) -> None:
        """Accept this file as-is."""
        self.user_decision = FileDecision.ACCEPT

    def reject(self) -> None:
        """Reject this file."""
        self.user_decision = FileDecision.REJECT

    def modify(self, new_content: str) -> None:
        """Modify this file with custom content."""
        self.user_decision = FileDecision.MODIFY
        self.modified_content = new_content


@dataclass
class GeneratedCode:
    """Collection of generated code for the integration."""

    playbook_id: str
    mapping_id: str
    generated_at: datetime = field(default_factory=datetime.now)

    # Generated files
    files: List[GeneratedFile] = field(default_factory=list)

    # Review status
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_at: Optional[datetime] = None

    # Application status
    applied: bool = False
    applied_at: Optional[datetime] = None

    @property
    def pending_review(self) -> List[GeneratedFile]:
        """Get files awaiting user decision."""
        return [f for f in self.files if f.user_decision is None]

    @property
    def accepted_files(self) -> List[GeneratedFile]:
        """Get accepted files."""
        return [f for f in self.files if f.user_decision in (FileDecision.ACCEPT, FileDecision.MODIFY)]

    @property
    def rejected_files(self) -> List[GeneratedFile]:
        """Get rejected files."""
        return [f for f in self.files if f.user_decision == FileDecision.REJECT]

    @property
    def all_decided(self) -> bool:
        """Check if all files have user decisions."""
        return all(f.user_decision is not None for f in self.files)

    def add_file(self, file: GeneratedFile) -> None:
        """Add a generated file."""
        self.files.append(file)

    def get_file(self, file_id: str) -> Optional[GeneratedFile]:
        """Get a file by ID."""
        for f in self.files:
            if f.id == file_id:
                return f
        return None

    def start_review(self) -> None:
        """Mark code as being reviewed."""
        self.review_status = ReviewStatus.IN_REVIEW

    def complete_review(self) -> None:
        """Mark review as complete."""
        if not self.all_decided:
            raise ValueError("Cannot complete review with pending decisions")
        if any(f.user_decision == FileDecision.MODIFY for f in self.files):
            self.review_status = ReviewStatus.MODIFIED
        elif any(f.user_decision == FileDecision.REJECT for f in self.files):
            self.review_status = ReviewStatus.REJECTED
        else:
            self.review_status = ReviewStatus.APPROVED
        self.reviewed_at = datetime.now()

    def mark_applied(self) -> None:
        """Mark code as applied."""
        self.applied = True
        self.applied_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "playbook_id": self.playbook_id,
            "mapping_id": self.mapping_id,
            "generated_at": self.generated_at.isoformat(),
            "files": [
                {
                    "id": f.id,
                    "file_path": str(f.file_path),
                    "file_type": f.file_type.value,
                    "content": f.content,
                    "is_modification": f.is_modification,
                    "original_content": f.original_content,
                    "diff": f.diff,
                    "user_decision": f.user_decision.value if f.user_decision else None,
                    "modified_content": f.modified_content,
                }
                for f in self.files
            ],
            "review_status": self.review_status.value,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "applied": self.applied,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedCode":
        """Deserialize from dictionary."""
        files = [
            GeneratedFile(
                id=f["id"],
                file_path=Path(f["file_path"]),
                file_type=FileType(f["file_type"]),
                content=f["content"],
                is_modification=f.get("is_modification", False),
                original_content=f.get("original_content"),
                diff=f.get("diff"),
                user_decision=FileDecision(f["user_decision"]) if f.get("user_decision") else None,
                modified_content=f.get("modified_content"),
            )
            for f in data.get("files", [])
        ]

        return cls(
            playbook_id=data["playbook_id"],
            mapping_id=data["mapping_id"],
            generated_at=datetime.fromisoformat(data["generated_at"]) if "generated_at" in data else datetime.now(),
            files=files,
            review_status=ReviewStatus(data.get("review_status", "pending")),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
            applied=data.get("applied", False),
            applied_at=datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None,
        )


@dataclass
class Patchset:
    """A cohesive set of files to apply together."""

    id: str
    generated_code_id: str
    created_at: datetime = field(default_factory=datetime.now)

    # Files to apply (only accepted/modified)
    files: List[GeneratedFile] = field(default_factory=list)

    # Application
    applied: bool = False
    applied_at: Optional[datetime] = None
    rollback_available: bool = False
    rollback_snapshot: Optional[str] = None  # Path to backup if available

    @classmethod
    def from_generated_code(cls, patchset_id: str, generated_code: GeneratedCode) -> "Patchset":
        """Create a patchset from reviewed generated code."""
        if not generated_code.all_decided:
            raise ValueError("Cannot create patchset from code with pending decisions")

        return cls(
            id=patchset_id,
            generated_code_id=generated_code.playbook_id,
            files=generated_code.accepted_files,
        )

    def apply(self, snapshot_path: Optional[str] = None) -> None:
        """Mark patchset as applied."""
        self.applied = True
        self.applied_at = datetime.now()
        if snapshot_path:
            self.rollback_available = True
            self.rollback_snapshot = snapshot_path

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "generated_code_id": self.generated_code_id,
            "created_at": self.created_at.isoformat(),
            "files": [
                {
                    "id": f.id,
                    "file_path": str(f.file_path),
                    "file_type": f.file_type.value,
                    "content": f.final_content,
                    "is_modification": f.is_modification,
                }
                for f in self.files
            ],
            "applied": self.applied,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rollback_available": self.rollback_available,
            "rollback_snapshot": self.rollback_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Patchset":
        """Deserialize from dictionary."""
        files = [
            GeneratedFile(
                id=f["id"],
                file_path=Path(f["file_path"]),
                file_type=FileType(f["file_type"]),
                content=f["content"],
                is_modification=f.get("is_modification", False),
            )
            for f in data.get("files", [])
        ]

        return cls(
            id=data["id"],
            generated_code_id=data["generated_code_id"],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            files=files,
            applied=data.get("applied", False),
            applied_at=datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None,
            rollback_available=data.get("rollback_available", False),
            rollback_snapshot=data.get("rollback_snapshot"),
        )
