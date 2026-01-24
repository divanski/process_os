"""
ProcessOS Artifact Registry

Stores artifacts externally with SHA256 content addressing.
Artifacts referenced by hash in state, stored in separate files.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class ArtifactRef:
    """Reference to a registered artifact."""
    artifact_id: str
    sha256: str
    kind: str
    size_bytes: int
    created_at: str
    step_id: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
        }
        if self.step_id:
            result["step_id"] = self.step_id
        if self.path:
            result["path"] = self.path
        return result


class ArtifactRegistry:
    """
    Content-addressed artifact storage.

    Features:
    - Store artifacts by SHA256 hash
    - Deduplicate identical content
    - Retrieve by ID or hash
    - List artifacts by kind or step
    """

    def __init__(self, artifacts_dir: Path):
        """
        Initialize registry.

        Args:
            artifacts_dir: Directory for artifact storage
        """
        self.artifacts_dir = artifacts_dir
        self._registry: Dict[str, ArtifactRef] = {}  # artifact_id -> ref
        self._by_hash: Dict[str, str] = {}  # sha256 -> artifact_id
        self._index_path = artifacts_dir / "registry.json"

        # Load existing registry
        self._load_index()

    def _load_index(self) -> None:
        """Load registry index from disk."""
        if self._index_path.exists():
            data = json.loads(self._index_path.read_text())
            for entry in data.get("artifacts", []):
                ref = ArtifactRef(**entry)
                self._registry[ref.artifact_id] = ref
                self._by_hash[ref.sha256] = ref.artifact_id

    def _save_index(self) -> None:
        """Save registry index to disk."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "artifacts": [ref.to_dict() for ref in sorted(
                self._registry.values(),
                key=lambda r: r.artifact_id
            )]
        }
        self._index_path.write_text(json.dumps(data, sort_keys=True, indent=2))

    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_artifact_id(self, sha256: str) -> str:
        """Generate artifact ID from hash."""
        return f"art-{sha256[:12]}"

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def register(
        self,
        content: str,
        kind: str,
        step_id: Optional[str] = None
    ) -> ArtifactRef:
        """
        Register an artifact.

        Args:
            content: Artifact content
            kind: Artifact kind/type
            step_id: Step that produced this artifact

        Returns:
            ArtifactRef with ID and hash
        """
        sha256 = self._compute_hash(content)

        # Check for existing artifact with same hash
        if sha256 in self._by_hash:
            return self._registry[self._by_hash[sha256]]

        # Create new artifact
        artifact_id = self._generate_artifact_id(sha256)
        artifact_path = self.artifacts_dir / f"{artifact_id}.txt"

        ref = ArtifactRef(
            artifact_id=artifact_id,
            sha256=sha256,
            kind=kind,
            size_bytes=len(content.encode()),
            created_at=self._now(),
            step_id=step_id,
            path=str(artifact_path.relative_to(self.artifacts_dir.parent)) if self.artifacts_dir.parent.exists() else str(artifact_path),
        )

        # Write content
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content)

        # Update registry
        self._registry[artifact_id] = ref
        self._by_hash[sha256] = artifact_id
        self._save_index()

        return ref

    def get(self, artifact_id: str) -> Optional[str]:
        """
        Get artifact content by ID.

        Args:
            artifact_id: Artifact identifier

        Returns:
            Content string or None if not found
        """
        if artifact_id not in self._registry:
            return None

        self._registry[artifact_id]
        artifact_path = self.artifacts_dir / f"{artifact_id}.txt"

        if not artifact_path.exists():
            return None

        return artifact_path.read_text()

    def get_by_hash(self, sha256: str) -> Optional[str]:
        """
        Get artifact content by SHA256 hash.

        Args:
            sha256: Content hash

        Returns:
            Content string or None if not found
        """
        if sha256 not in self._by_hash:
            return None
        return self.get(self._by_hash[sha256])

    def get_ref(self, artifact_id: str) -> Optional[ArtifactRef]:
        """Get artifact reference by ID."""
        return self._registry.get(artifact_id)

    def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists."""
        return artifact_id in self._registry

    def exists_by_hash(self, sha256: str) -> bool:
        """Check if artifact exists by hash."""
        return sha256 in self._by_hash

    def find_by_kind(self, kind: str) -> List[ArtifactRef]:
        """Find artifacts by kind."""
        return sorted(
            [ref for ref in self._registry.values() if ref.kind == kind],
            key=lambda r: r.artifact_id
        )

    def find_by_step(self, step_id: str) -> List[ArtifactRef]:
        """Find artifacts by step."""
        return sorted(
            [ref for ref in self._registry.values() if ref.step_id == step_id],
            key=lambda r: r.artifact_id
        )

    def verify(self, artifact_id: str) -> bool:
        """
        Verify artifact integrity.

        Args:
            artifact_id: Artifact to verify

        Returns:
            True if content matches stored hash
        """
        if artifact_id not in self._registry:
            return False

        ref = self._registry[artifact_id]
        content = self.get(artifact_id)

        if content is None:
            return False

        return self._compute_hash(content) == ref.sha256

    def list_all(self) -> List[ArtifactRef]:
        """List all registered artifacts."""
        return sorted(self._registry.values(), key=lambda r: r.artifact_id)

    def get_manifest(self) -> Dict[str, Any]:
        """Get registry manifest."""
        return {
            "artifact_count": len(self._registry),
            "total_size_bytes": sum(ref.size_bytes for ref in self._registry.values()),
            "artifacts": [ref.to_dict() for ref in self.list_all()],
        }
