"""
ProcessOS Stack Fingerprint

Generates deterministic fingerprints for detected stacks.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .detector import DetectedFramework, DetectedStack, DetectionResult, StackDetector
from .version_extractor import DetailedFingerprint, VersionExtractor


@dataclass
class StackFingerprint:
    """
    Deterministic fingerprint of a project's technology stack.

    Same project state always produces the same fingerprint_id.
    """

    fingerprint_id: str
    detected_at: str
    project_root: str
    stacks: List[Dict[str, Any]]
    frameworks: List[Dict[str, Any]]
    content_hash: str
    details: Optional[Dict[str, Any]] = None  # Detailed version info

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "fingerprint_id": self.fingerprint_id,
            "detected_at": self.detected_at,
            "project_root": self.project_root,
            "stacks": self.stacks,
            "frameworks": self.frameworks,
            "content_hash": self.content_hash,
        }
        if self.details:
            result["details"] = self.details
        return result

    def to_yaml(self) -> str:
        """Serialize to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StackFingerprint":
        """Create from dictionary."""
        return cls(
            fingerprint_id=data["fingerprint_id"],
            detected_at=data["detected_at"],
            project_root=data["project_root"],
            stacks=data["stacks"],
            frameworks=data["frameworks"],
            content_hash=data["content_hash"],
            details=data.get("details"),
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "StackFingerprint":
        """Create from YAML string."""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)

    def get_stack_ids(self) -> List[str]:
        """Get list of detected stack IDs."""
        return [s["stack_id"] for s in self.stacks]

    def get_framework_ids(self) -> List[str]:
        """Get list of detected framework IDs."""
        return [f["framework_id"] for f in self.frameworks]

    def has_stack(self, stack_id: str) -> bool:
        """Check if a stack was detected."""
        return stack_id in self.get_stack_ids()

    def has_framework(self, framework_id: str) -> bool:
        """Check if a framework was detected."""
        return framework_id in self.get_framework_ids()


class FingerprintGenerator:
    """
    Generates deterministic fingerprints for projects.

    Key invariant: same project state → same fingerprint_id
    """

    def __init__(self, max_depth: int = 2):
        """
        Initialize generator.

        Args:
            max_depth: Maximum depth for stack detection
        """
        self.detector = StackDetector(max_depth=max_depth)

    def generate(
        self,
        project_root: Path,
        timestamp: Optional[str] = None,
        include_details: bool = True,
    ) -> StackFingerprint:
        """
        Generate fingerprint for a project.

        Args:
            project_root: Path to project root
            timestamp: Optional fixed timestamp (for determinism in tests)
            include_details: Whether to extract detailed version info

        Returns:
            StackFingerprint
        """
        project_root = Path(project_root).resolve()

        # Detect stacks
        result = self.detector.detect(project_root)

        # Convert to sorted dicts for deterministic hashing
        stacks = sorted(
            [s.to_dict() for s in result.stacks],
            key=lambda x: x["stack_id"],
        )
        frameworks = sorted(
            [f.to_dict() for f in result.frameworks],
            key=lambda x: (x["stack"], x["framework_id"]),
        )

        # Extract detailed version information
        details = None
        if include_details:
            extractor = VersionExtractor(project_root)
            detailed_fp = extractor.extract()
            details = detailed_fp.to_dict()

        # Generate content hash (deterministic)
        content_hash = self._compute_content_hash(stacks, frameworks)

        # Generate fingerprint ID from content
        fingerprint_id = f"fp-{content_hash[:12]}"

        # Use provided timestamp or current time
        detected_at = timestamp or datetime.now(timezone.utc).isoformat()

        return StackFingerprint(
            fingerprint_id=fingerprint_id,
            detected_at=detected_at,
            project_root=str(project_root),
            stacks=stacks,
            frameworks=frameworks,
            content_hash=f"sha256:{content_hash}",
            details=details,
        )

    def _compute_content_hash(
        self,
        stacks: List[Dict[str, Any]],
        frameworks: List[Dict[str, Any]],
    ) -> str:
        """Compute deterministic content hash."""
        # Use JSON for deterministic serialization
        content = json.dumps(
            {"stacks": stacks, "frameworks": frameworks},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_fingerprint(
    project_root: Path,
    timestamp: Optional[str] = None,
) -> StackFingerprint:
    """
    Convenience function to generate a fingerprint.

    Args:
        project_root: Path to project root
        timestamp: Optional fixed timestamp

    Returns:
        StackFingerprint
    """
    generator = FingerprintGenerator()
    return generator.generate(project_root, timestamp=timestamp)
