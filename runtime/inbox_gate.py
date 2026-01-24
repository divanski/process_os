"""
ProcessOS Inbox Gate

Checks for required user-provided materials before proceeding.
Used to halt runs awaiting API docs, credentials, etc. for integrations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple


@dataclass
class InboxGateConfig:
    """Configuration for inbox materials gate."""

    integration_id: str  # e.g., "autopartsplus", "stripe" (any service)
    required_one_of: List[str] = field(default_factory=lambda: [
        "*.postman_collection.json",
        "openapi.yaml",
        "openapi.json",
        "swagger.yaml",
        "swagger.json",
        "curl_examples.md",
        "api_docs.md",
    ])
    require_secrets_file: bool = True


@dataclass
class InboxGateResult:
    """Result of inbox gate check."""

    passed: bool
    missing_items: List[str]
    found_items: List[str]
    secrets_file_exists: bool
    resume_instructions: str


class InboxGate:
    """
    Gate that checks for required inbox materials.

    Halts execution if materials are missing, allowing user to provide them.
    """

    def __init__(self, processos_dir: Path, config: InboxGateConfig):
        """
        Initialize inbox gate.

        Args:
            processos_dir: Path to .processos directory
            config: Gate configuration
        """
        self.processos_dir = Path(processos_dir)
        self.config = config

        # Derive paths - generic integration directory structure
        self.inbox_dir = self.processos_dir / "inbox" / "integrations" / config.integration_id
        self.secrets_file = self.processos_dir / "secrets" / f"integration_{config.integration_id}.env"

    def check(self) -> InboxGateResult:
        """
        Check if required materials are present.

        Returns:
            InboxGateResult with pass/fail status and details
        """
        found_items: List[str] = []
        missing_items: List[str] = []

        # Check for at least one of the required docs
        docs_found = False
        if self.inbox_dir.exists():
            for pattern in self.config.required_one_of:
                matches = list(self.inbox_dir.glob(pattern))
                if matches:
                    docs_found = True
                    found_items.extend(str(m.name) for m in matches)

        if not docs_found:
            missing_items.append(
                f"API docs (one of: {', '.join(self.config.required_one_of)})"
            )

        # Check secrets file exists (do NOT read contents)
        secrets_exists = self.secrets_file.exists() if self.config.require_secrets_file else True

        if self.config.require_secrets_file and not secrets_exists:
            missing_items.append(f"Credentials file: {self.secrets_file.relative_to(self.processos_dir.parent)}")

        # Build resume instructions
        resume_instructions = self._build_resume_instructions(missing_items)

        passed = len(missing_items) == 0

        return InboxGateResult(
            passed=passed,
            missing_items=missing_items,
            found_items=found_items,
            secrets_file_exists=secrets_exists,
            resume_instructions=resume_instructions,
        )

    def _build_resume_instructions(self, missing_items: List[str]) -> str:
        """Build human-readable resume instructions."""
        if not missing_items:
            return "All materials present. Ready to proceed."

        lines = [
            f"To resume integration for {self.config.integration_id.upper()}:",
            "",
            "1. Provide the following:",
        ]

        for item in missing_items:
            lines.append(f"   - {item}")

        lines.extend([
            "",
            f"2. Drop files into: {self.inbox_dir.relative_to(self.processos_dir.parent)}/",
            "",
            "3. Re-run the same command:",
            f'   processos cmd "integrate {self.config.integration_id}" --host .',
            "",
        ])

        return "\n".join(lines)


def check_inbox_materials(
    processos_dir: Path,
    integration_id: str,
) -> Tuple[bool, InboxGateResult]:
    """
    Convenience function to check inbox materials.

    Args:
        processos_dir: Path to .processos directory
        integration_id: Integration identifier (lowercase)

    Returns:
        Tuple of (passed, result)
    """
    config = InboxGateConfig(integration_id=integration_id)
    gate = InboxGate(processos_dir, config)
    result = gate.check()
    return result.passed, result
