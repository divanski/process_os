"""
ProcessOS Ship Guardrails

Tests that verify the repository does not contain forbidden paths.
These paths should never be committed to git.
"""

import subprocess
from pathlib import Path


# Forbidden path patterns that should never be tracked in git
FORBIDDEN_PATHS = [
    # Runtime state
    ".processos/",
    "process_os_output/",
    "process_os/runtime/runs/",

    # Development extras (moved out of ship set)
    "process_os/docs/",
    "process_os/demo/",
    "process_os/demos/",

    # Secrets and environment
    "process_os/.env",
    ".env",
]

# Workspace pattern (special handling)
WORKSPACE_PATTERN = "process_os/workspaces/ws-"


def get_tracked_files() -> list[str]:
    """Get list of all files tracked by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        # Not in a git repo or git not available
        return []
    except FileNotFoundError:
        # Git not installed
        return []


class TestShipGuardrails:
    """Guardrail tests to prevent committing forbidden paths."""

    def test_no_forbidden_paths_tracked(self):
        """Ensure no forbidden paths are tracked in git."""
        tracked_files = get_tracked_files()

        if not tracked_files:
            # Skip if not in git repo
            return

        violations = []
        for tracked_file in tracked_files:
            # Check forbidden path prefixes
            for forbidden in FORBIDDEN_PATHS:
                if tracked_file.startswith(forbidden) or tracked_file == forbidden.rstrip("/"):
                    violations.append(f"{tracked_file} (matches {forbidden})")
                    break

            # Check workspace pattern
            if WORKSPACE_PATTERN in tracked_file:
                violations.append(f"{tracked_file} (matches {WORKSPACE_PATTERN})")

        assert not violations, (
            f"Forbidden paths are tracked in git:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nThese paths should be in .gitignore and not committed."
        )

    def test_no_processos_runtime_state(self):
        """Ensure .processos directory is not tracked."""
        tracked_files = get_tracked_files()

        if not tracked_files:
            return

        processos_files = [f for f in tracked_files if f.startswith(".processos/")]

        assert not processos_files, (
            f".processos/ runtime state is tracked in git:\n"
            + "\n".join(f"  - {f}" for f in processos_files[:10])
            + ("\n  ..." if len(processos_files) > 10 else "")
            + "\n\nThe .processos/ directory should never be committed."
        )

    def test_no_real_env_file(self):
        """Ensure .env files with secrets are not tracked."""
        tracked_files = get_tracked_files()

        if not tracked_files:
            return

        # .env at root or in process_os/ (but .env.example is OK)
        env_files = [
            f for f in tracked_files
            if (f == ".env" or f == "process_os/.env")
            and not f.endswith(".example")
        ]

        assert not env_files, (
            f"Real .env files are tracked in git:\n"
            + "\n".join(f"  - {f}" for f in env_files)
            + "\n\nOnly .env.example should be committed, not real .env files."
        )

    def test_env_example_exists(self):
        """Ensure .env.example template exists."""
        repo_root = Path(__file__).parent.parent.parent
        env_example = repo_root / "process_os" / ".env.example"

        assert env_example.exists(), (
            "process_os/.env.example must exist as a template for environment variables."
        )

    def test_docs_not_in_process_os(self):
        """Ensure process_os/docs is moved to extras/."""
        repo_root = Path(__file__).parent.parent.parent
        forbidden_docs = repo_root / "process_os" / "docs"

        assert not forbidden_docs.exists(), (
            f"process_os/docs/ should not exist.\n"
            f"It should be moved to extras/docs/ for the ship build."
        )

    def test_demo_not_in_process_os(self):
        """Ensure process_os/demo is moved to extras/."""
        repo_root = Path(__file__).parent.parent.parent
        forbidden_demo = repo_root / "process_os" / "demo"

        assert not forbidden_demo.exists(), (
            f"process_os/demo/ should not exist.\n"
            f"It should be moved to extras/demo/ for the ship build."
        )

    def test_demos_not_in_process_os(self):
        """Ensure process_os/demos is moved to extras/."""
        repo_root = Path(__file__).parent.parent.parent
        forbidden_demos = repo_root / "process_os" / "demos"

        assert not forbidden_demos.exists(), (
            f"process_os/demos/ should not exist.\n"
            f"It should be moved to extras/demos/ for the ship build."
        )
