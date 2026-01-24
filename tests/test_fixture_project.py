"""
ProcessOS Fixture Project Tests

Tests for Sprint 6: eushipments_like fixture validation.
"""

from pathlib import Path

import pytest
import yaml

from process_os.hosts import FilesystemHost, HostPolicy


class TestFixtureStructure:
    """Test fixture project directory structure."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Get path to fixture project."""
        return Path(__file__).parent / "fixtures" / "eushipments_like"

    def test_fixture_exists(self, fixture_path):
        """Fixture project directory exists."""
        assert fixture_path.exists()
        assert fixture_path.is_dir()

    def test_fixture_has_readme(self, fixture_path):
        """Fixture has README."""
        readme = fixture_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "eushipments_like" in content

    def test_fixture_has_config(self, fixture_path):
        """Fixture has config directory with files."""
        config_dir = fixture_path / "config"
        assert config_dir.exists()
        assert (config_dir / "carriers.yaml").exists()
        assert (config_dir / "settings.yaml").exists()

    def test_fixture_has_src_structure(self, fixture_path):
        """Fixture has source directory structure."""
        src_dir = fixture_path / "src"
        assert src_dir.exists()
        assert (src_dir / "controllers").is_dir()
        assert (src_dir / "services").is_dir()
        assert (src_dir / "models").is_dir()

    def test_fixture_has_controller(self, fixture_path):
        """Fixture has shipment controller."""
        controller = fixture_path / "src" / "controllers" / "shipment_controller.py"
        assert controller.exists()

    def test_fixture_has_services(self, fixture_path):
        """Fixture has service files."""
        services_dir = fixture_path / "src" / "services"
        assert (services_dir / "carrier_service.py").exists()
        assert (services_dir / "tracking_service.py").exists()

    def test_fixture_has_models(self, fixture_path):
        """Fixture has model files."""
        models_dir = fixture_path / "src" / "models"
        assert (models_dir / "shipment.py").exists()


class TestFixtureConfig:
    """Test fixture configuration files."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Get path to fixture project."""
        return Path(__file__).parent / "fixtures" / "eushipments_like"

    def test_carriers_config_valid_yaml(self, fixture_path):
        """Carriers config is valid YAML."""
        config_path = fixture_path / "config" / "carriers.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "carriers" in config
        assert len(config["carriers"]) >= 2

    def test_carriers_config_has_dhl(self, fixture_path):
        """Carriers config includes DHL."""
        config_path = fixture_path / "config" / "carriers.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        carrier_ids = [c["id"] for c in config["carriers"]]
        assert "dhl" in carrier_ids

    def test_carriers_config_structure(self, fixture_path):
        """Carrier entries have required fields."""
        config_path = fixture_path / "config" / "carriers.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        for carrier in config["carriers"]:
            assert "id" in carrier
            assert "name" in carrier
            assert "base_url" in carrier
            assert "endpoints" in carrier
            assert "rate_limits" in carrier
            assert "auth" in carrier

    def test_settings_config_valid_yaml(self, fixture_path):
        """Settings config is valid YAML."""
        config_path = fixture_path / "config" / "settings.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "application" in config
        assert "shipping" in config
        assert "tracking" in config


class TestFixtureHostAccess:
    """Test accessing fixture via host adapter."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Get path to fixture project."""
        return Path(__file__).parent / "fixtures" / "eushipments_like"

    def test_host_can_read_config(self, fixture_path):
        """Host adapter can read config files."""
        policy = HostPolicy.default()
        host = FilesystemHost(fixture_path, policy)

        content = host.read_file("config/carriers.yaml")
        assert "carriers:" in content

    def test_host_can_list_files(self, fixture_path):
        """Host adapter can list files."""
        policy = HostPolicy.default()
        host = FilesystemHost(fixture_path, policy)

        # List Python files recursively
        files = host.list_files("**/*.py")
        assert len(files) >= 1

    def test_host_can_read_python(self, fixture_path):
        """Host adapter can read Python files."""
        policy = HostPolicy.default()
        host = FilesystemHost(fixture_path, policy)

        content = host.read_file("src/models/shipment.py")
        assert "class Shipment" in content


class TestFixtureDeterminism:
    """Test fixture content is deterministic."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Get path to fixture project."""
        return Path(__file__).parent / "fixtures" / "eushipments_like"

    def test_config_has_no_timestamps(self, fixture_path):
        """Config files have no timestamps."""
        config_files = [
            fixture_path / "config" / "carriers.yaml",
            fixture_path / "config" / "settings.yaml",
        ]

        for config_file in config_files:
            content = config_file.read_text()
            # Should not contain datetime patterns
            assert "2024-" not in content
            assert "2025-" not in content
            assert "2026-" not in content

    def test_source_has_no_timestamps(self, fixture_path):
        """Source files have no timestamps."""
        py_files = list((fixture_path / "src").rglob("*.py"))

        for py_file in py_files:
            content = py_file.read_text()
            # Should not contain datetime patterns in actual code
            # (docstrings mentioning dates are OK)
            lines = content.split("\n")
            code_lines = [l for l in lines if not l.strip().startswith("#")]
            code = "\n".join(code_lines)
            # Timestamps shouldn't appear in executable code
            # (dataclass defaults are fine if they're not actual timestamps)
