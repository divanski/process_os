"""
Shared pytest fixtures for ProcessOS CI/CL Client Integration tests.

Provides:
- Temporary directories for test isolation
- Sample project fixtures (Laravel, Django, etc.)
- Mock WebSocket server fixtures
- Pre-recorded audit data fixtures
- Database fixtures for testing
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_processos_dir(temp_dir: Path) -> Path:
    """Provide a temporary .processos directory."""
    processos_dir = temp_dir / ".processos"
    processos_dir.mkdir(parents=True, exist_ok=True)
    return processos_dir


@pytest.fixture
def temp_audit_dir(temp_processos_dir: Path) -> Path:
    """Provide a temporary .processos/audit directory."""
    audit_dir = temp_processos_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


@pytest.fixture
def sample_laravel_project(temp_dir: Path) -> Path:
    """
    Create a minimal Laravel project structure for testing.

    Contains essential files to trigger framework detection.
    """
    project = temp_dir / "laravel-simple"
    project.mkdir()

    # Create composer.json
    composer_json = {
        "name": "laravel/laravel",
        "description": "The Laravel Framework.",
        "require": {
            "php": "^8.0",
            "laravel/framework": "^9.0",
        },
    }
    (project / "composer.json").write_text(json.dumps(composer_json, indent=2))

    # Create artisan file (Laravel CLI)
    (project / "artisan").write_text("#!/usr/bin/env php\n<?php // Laravel artisan file")

    # Create app directory structure
    app_dir = project / "app"
    app_dir.mkdir()
    (app_dir / "Http").mkdir()
    (app_dir / "Http" / "Controllers").mkdir()
    (app_dir / "Services").mkdir()
    (app_dir / "Models").mkdir()

    # Create sample PHP files
    (app_dir / "Http" / "Controllers" / "HomeController.php").write_text(
        """<?php
namespace App\\Http\\Controllers;

class HomeController {
    public function index() {
        return view('home');
    }
}
"""
    )

    (app_dir / "Services" / "UserService.php").write_text(
        """<?php
namespace App\\Services;

class UserService {
    public function getUserById($id) {
        return User::find($id);
    }
}
"""
    )

    # Create config directory
    config_dir = project / "config"
    config_dir.mkdir()
    (config_dir / "app.php").write_text("<?php\nreturn [];")

    return project


@pytest.fixture
def sample_django_project(temp_dir: Path) -> Path:
    """
    Create a minimal Django project structure for testing.

    Contains essential files to trigger framework detection.
    """
    project = temp_dir / "django-simple"
    project.mkdir()

    # Create manage.py
    (project / "manage.py").write_text(
        """#!/usr/bin/env python
import django
# Django management script
"""
    )

    # Create requirements.txt
    (project / "requirements.txt").write_text("Django==4.2\n")

    # Create project structure
    app_dir = project / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("")
    (app_dir / "models.py").write_text("")
    (app_dir / "views.py").write_text("")

    # Create settings
    settings_dir = project / "settings"
    settings_dir.mkdir()
    (settings_dir / "base.py").write_text("")

    return project


@pytest.fixture
def mock_audit_entries() -> list[dict]:
    """Provide pre-recorded audit entries for testing."""
    return [
        {
            "entry_id": "550e8400-e29b-41d4-a716-446655440001",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-01-25T10:00:00Z",
            "project_id": "abc123",
            "event_type": "analysis_started",
            "user_id": "developer@example.com",
            "event_metadata": {},
        },
        {
            "entry_id": "550e8400-e29b-41d4-a716-446655440002",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-01-25T10:00:30Z",
            "project_id": "abc123",
            "event_type": "language_detected",
            "user_id": "developer@example.com",
            "detected_language": "PHP",
            "confidence_score": 0.98,
        },
        {
            "entry_id": "550e8400-e29b-41d4-a716-446655440003",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-01-25T10:00:45Z",
            "project_id": "abc123",
            "event_type": "framework_detected",
            "user_id": "developer@example.com",
            "detected_framework": "Laravel",
            "confidence_score": 0.95,
        },
        {
            "entry_id": "550e8400-e29b-41d4-a716-446655440004",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-01-25T10:01:00Z",
            "project_id": "abc123",
            "event_type": "analysis_completed",
            "user_id": "developer@example.com",
            "event_metadata": {"overall_confidence": 0.95},
        },
    ]


@pytest.fixture
def processos_config(temp_processos_dir: Path) -> dict:
    """Provide a minimal .processos configuration."""
    return {
        "version": "1.0.0",
        "project_id": "test-project-hash",
        "initialized_at": "2026-01-25T10:00:00Z",
        "audit_key": "test-encryption-key",
    }


@pytest.fixture
def monkeypatch_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Provide monkeypatch for environment variables."""
    monkeypatch.setenv("PROCESSOS_AUDIT_KEY", "test-key-32-chars-long-for-aes--")
    monkeypatch.setenv("PROCESSOS_ROLE", "DEVELOPER")
    monkeypatch.setenv("PROCESSOS_USER_ID", "test-user")
    return monkeypatch
