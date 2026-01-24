"""
ProcessOS Host Adapter Tests

Tests for S5-001: Host adapter with policy enforcement.
"""

import tempfile
from pathlib import Path

import pytest

from process_os.hosts import (
    FilesystemHost,
    HostAccessDenied,
    HostPolicy,
    MockHostAdapter,
)


class TestHostPolicy:
    """Host policy tests."""

    def test_default_policy_denies_git(self):
        """Default policy denies .git access."""
        policy = HostPolicy.default()
        assert policy.matches_denylist(".git/config")
        assert policy.matches_denylist(".git")

    def test_default_policy_denies_env(self):
        """Default policy denies .env files."""
        policy = HostPolicy.default()
        assert policy.matches_denylist(".env")
        assert policy.matches_denylist(".env.local")

    def test_default_policy_denies_secrets(self):
        """Default policy denies secrets directories."""
        policy = HostPolicy.default()
        assert policy.matches_denylist("config/secrets/api.key")
        assert policy.matches_denylist("credentials/token.json")

    def test_default_policy_allows_python_files(self):
        """Default policy allows Python files."""
        policy = HostPolicy.default()
        assert policy.matches_allowlist("main.py")
        assert policy.matches_allowlist("src/app.py")

    def test_default_policy_allows_json_files(self):
        """Default policy allows JSON files."""
        policy = HostPolicy.default()
        assert policy.matches_allowlist("config.json")
        assert policy.matches_allowlist("package.json")


class TestFilesystemHost:
    """Filesystem host adapter tests."""

    def test_read_allowed_file(self):
        """Can read files in allowlist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.py"
            test_file.write_text("# Test content")

            host = FilesystemHost(tmppath)
            content = host.read_file("test.py")

            assert content == "# Test content"

    def test_read_denied_file_raises(self):
        """Reading denied files raises HostAccessDenied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            env_file = tmppath / ".env"
            env_file.write_text("SECRET=value")

            host = FilesystemHost(tmppath)

            with pytest.raises(HostAccessDenied) as exc:
                host.read_file(".env")

            assert exc.value.reason == "denylist"

    def test_read_nonexistent_file_raises(self):
        """Reading nonexistent file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            host = FilesystemHost(Path(tmpdir))

            with pytest.raises(FileNotFoundError):
                host.read_file("nonexistent.py")

    def test_path_escape_denied(self):
        """Paths escaping root are denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            host = FilesystemHost(Path(tmpdir))

            with pytest.raises(HostAccessDenied):
                host.read_file("../../../etc/passwd")

    def test_file_exists_allowed(self):
        """file_exists works for allowed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.py"
            test_file.write_text("content")

            host = FilesystemHost(tmppath)

            assert host.file_exists("test.py") is True
            assert host.file_exists("nonexistent.py") is False

    def test_file_exists_denied_returns_false(self):
        """file_exists returns False for denied paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            env_file = tmppath / ".env"
            env_file.write_text("SECRET=value")

            host = FilesystemHost(tmppath)

            # Denied paths are treated as non-existent
            assert host.file_exists(".env") is False

    def test_list_files_filters_denied(self):
        """list_files excludes denied patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.py").write_text("content")
            (tmppath / ".env").write_text("secret")

            host = FilesystemHost(tmppath)
            files = host.list_files("*")

            assert "test.py" in files
            assert ".env" not in files

    def test_access_log_recorded(self):
        """File accesses are logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.py"
            test_file.write_text("content")

            host = FilesystemHost(tmppath)
            host.read_file("test.py")

            log = host.get_access_log()
            assert len(log) == 1
            assert log[0]["path"] == "test.py"
            assert log[0]["operation"] == "read"
            assert log[0]["success"] is True

    def test_size_limit_enforced(self):
        """Files exceeding size limit are denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create file larger than default limit (500KB)
            big_file = tmppath / "big.txt"
            big_file.write_text("x" * (600 * 1024))

            host = FilesystemHost(tmppath)

            with pytest.raises(HostAccessDenied) as exc:
                host.read_file("big.txt")

            assert exc.value.reason == "size_exceeded"


class TestMockHostAdapter:
    """Mock host adapter tests."""

    def test_mock_read_file(self):
        """Mock adapter returns configured content."""
        mock = MockHostAdapter({"test.py": "mock content"})
        content = mock.read_file("test.py")
        assert content == "mock content"

    def test_mock_file_not_found(self):
        """Mock adapter raises for missing files."""
        mock = MockHostAdapter({})

        with pytest.raises(FileNotFoundError):
            mock.read_file("nonexistent.py")

    def test_mock_add_file(self):
        """Can add files to mock adapter."""
        mock = MockHostAdapter()
        mock.add_file("new.py", "new content")

        assert mock.read_file("new.py") == "new content"

    def test_mock_policy_enforcement(self):
        """Mock adapter enforces policy."""
        mock = MockHostAdapter(
            {".env": "secret"},
            policy=HostPolicy(
                mode="denylist",
                denylist_patterns=[".env*"],
            ),
        )

        with pytest.raises(HostAccessDenied):
            mock.read_file(".env")

    def test_mock_list_files(self):
        """Mock adapter lists files."""
        mock = MockHostAdapter({
            "src/main.py": "content",
            "src/utils.py": "content",
            "test.py": "content",
        })

        files = mock.list_files("src/*.py")
        assert "src/main.py" in files
        assert "src/utils.py" in files
        assert "test.py" not in files
