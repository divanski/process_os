"""
ProcessOS Version Extractor

Extracts detailed version information from project configuration files.
Provides comprehensive stack fingerprinting for code generation.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class VersionInfo:
    """Version information for a component."""

    name: str
    version: str
    version_constraint: Optional[str] = None  # Original constraint like "^5.6"
    resolved_version: Optional[str] = None    # Actual installed version

    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "version": self.version}
        if self.version_constraint:
            result["constraint"] = self.version_constraint
        if self.resolved_version:
            result["resolved"] = self.resolved_version
        return result


@dataclass
class DatabaseInfo:
    """Database configuration details."""

    type: str  # mysql, postgresql, sqlite, firebird, etc.
    driver: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type}
        if self.driver:
            result["driver"] = self.driver
        if self.version:
            result["version"] = self.version
        return result


@dataclass
class DetailedFingerprint:
    """Comprehensive stack fingerprint with version details."""

    # Core language/runtime versions
    php_version: Optional[VersionInfo] = None
    node_version: Optional[VersionInfo] = None
    python_version: Optional[VersionInfo] = None

    # Framework versions
    framework: Optional[VersionInfo] = None
    framework_type: Optional[str] = None  # laravel, django, express, etc.

    # Build tools
    build_tool: Optional[VersionInfo] = None  # webpack, vite, laravel-mix, etc.
    package_manager: Optional[str] = None     # npm, yarn, pnpm, composer

    # Database
    database: Optional[DatabaseInfo] = None

    # Key dependencies that affect code generation
    key_dependencies: List[VersionInfo] = field(default_factory=list)

    # Frontend stack
    css_framework: Optional[VersionInfo] = None  # bootstrap, tailwind
    js_framework: Optional[VersionInfo] = None   # vue, react, jquery

    # Testing frameworks
    test_framework: Optional[VersionInfo] = None

    # Additional metadata
    has_typescript: bool = False
    has_docker: bool = False
    has_ci: bool = False
    module_system: Optional[str] = None  # esm, commonjs, modules (laravel-modules)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: Dict[str, Any] = {}

        # Core versions
        if self.php_version:
            result["php"] = self.php_version.to_dict()
        if self.node_version:
            result["node"] = self.node_version.to_dict()
        if self.python_version:
            result["python"] = self.python_version.to_dict()

        # Framework
        if self.framework:
            result["framework"] = {
                "type": self.framework_type,
                **self.framework.to_dict()
            }

        # Build tool
        if self.build_tool:
            result["build_tool"] = self.build_tool.to_dict()
        if self.package_manager:
            result["package_manager"] = self.package_manager

        # Database
        if self.database:
            result["database"] = self.database.to_dict()

        # Key dependencies
        if self.key_dependencies:
            result["key_dependencies"] = [d.to_dict() for d in self.key_dependencies]

        # Frontend
        frontend = {}
        if self.css_framework:
            frontend["css"] = self.css_framework.to_dict()
        if self.js_framework:
            frontend["js"] = self.js_framework.to_dict()
        if frontend:
            result["frontend"] = frontend

        # Testing
        if self.test_framework:
            result["testing"] = self.test_framework.to_dict()

        # Flags
        flags = []
        if self.has_typescript:
            flags.append("typescript")
        if self.has_docker:
            flags.append("docker")
        if self.has_ci:
            flags.append("ci")
        if flags:
            result["features"] = flags

        if self.module_system:
            result["module_system"] = self.module_system

        return result


class VersionExtractor:
    """Extracts detailed version information from project files."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.fingerprint = DetailedFingerprint()

    def extract(self) -> DetailedFingerprint:
        """Extract all version information."""
        self._extract_from_pyproject()  # Python projects
        self._extract_from_requirements()  # Python requirements.txt
        self._extract_from_composer()  # PHP projects
        self._extract_from_package_json()  # Node.js projects
        self._extract_from_env()
        self._extract_from_lockfiles()
        self._detect_features()
        return self.fingerprint

    def _read_json(self, filename: str) -> Optional[Dict]:
        """Read and parse a JSON file."""
        filepath = self.project_root / filename
        if filepath.exists():
            try:
                return json.loads(filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _read_text(self, filename: str) -> Optional[str]:
        """Read a text file."""
        filepath = self.project_root / filename
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8")
            except OSError:
                pass
        return None

    def _extract_from_pyproject(self) -> None:
        """Extract Python version and dependencies from pyproject.toml."""
        content = self._read_text("pyproject.toml")
        if not content:
            return

        # Python version from requires-python
        python_match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
        if python_match:
            python_constraint = python_match.group(1)
            self.fingerprint.python_version = VersionInfo(
                name="python",
                version=self._parse_version_constraint(python_constraint),
                version_constraint=python_constraint
            )

        # Check .python-version file as fallback
        if not self.fingerprint.python_version:
            py_version = self._read_text(".python-version")
            if py_version:
                version = py_version.strip().split("\n")[0].strip()
                self.fingerprint.python_version = VersionInfo(
                    name="python",
                    version=version
                )

        # Extract dependencies section
        deps_section = re.search(r'\[project\.dependencies\](.*?)(?=\[|\Z)', content, re.DOTALL)
        deps_text = deps_section.group(1) if deps_section else content

        # Django detection
        django_match = re.search(r'["\']?django["\']?\s*[>=<~!]*\s*(["\']?)([^"\'>\s,\]]+)', deps_text, re.IGNORECASE)
        if django_match:
            version = django_match.group(2) if django_match.group(2) else "unknown"
            self.fingerprint.framework = VersionInfo(
                name="django",
                version=self._parse_version_constraint(version),
                version_constraint=version
            )
            self.fingerprint.framework_type = "django"

        # FastAPI detection
        fastapi_match = re.search(r'["\']?fastapi["\']?\s*[>=<~!]*\s*(["\']?)([^"\'>\s,\]]+)', deps_text, re.IGNORECASE)
        if fastapi_match and not self.fingerprint.framework:
            version = fastapi_match.group(2) if fastapi_match.group(2) else "unknown"
            self.fingerprint.framework = VersionInfo(
                name="fastapi",
                version=self._parse_version_constraint(version),
                version_constraint=version
            )
            self.fingerprint.framework_type = "fastapi"

        # Flask detection
        flask_match = re.search(r'["\']?flask["\']?\s*[>=<~!]*\s*(["\']?)([^"\'>\s,\]]+)', deps_text, re.IGNORECASE)
        if flask_match and not self.fingerprint.framework:
            version = flask_match.group(2) if flask_match.group(2) else "unknown"
            self.fingerprint.framework = VersionInfo(
                name="flask",
                version=self._parse_version_constraint(version),
                version_constraint=version
            )
            self.fingerprint.framework_type = "flask"

        # Key Python dependencies
        key_python_deps = [
            ("pytest", "pytest"),
            ("django-rest-framework", "djangorestframework"),
            ("celery", "celery"),
            ("redis", "redis"),
            ("sqlalchemy", "sqlalchemy"),
            ("alembic", "alembic"),
            ("pydantic", "pydantic"),
            ("httpx", "httpx"),
            ("requests", "requests"),
            ("boto3", "boto3"),
            ("sentry-sdk", "sentry-sdk"),
        ]

        for dep_name, search_name in key_python_deps:
            dep_match = re.search(rf'["\']?{search_name}["\']?\s*[>=<~!]*\s*["\']?([^"\'>\s,\]]*)', deps_text, re.IGNORECASE)
            if dep_match:
                version = dep_match.group(1) if dep_match.group(1) else "unknown"
                self.fingerprint.key_dependencies.append(VersionInfo(
                    name=dep_name,
                    version=self._parse_version_constraint(version),
                    version_constraint=version if version != "unknown" else None
                ))

        # Test framework
        if re.search(r'pytest', deps_text, re.IGNORECASE):
            pytest_match = re.search(r'pytest["\']?\s*[>=<~!]*\s*["\']?([^"\'>\s,\]]*)', deps_text, re.IGNORECASE)
            version = pytest_match.group(1) if pytest_match and pytest_match.group(1) else "unknown"
            self.fingerprint.test_framework = VersionInfo(
                name="pytest",
                version=self._parse_version_constraint(version),
                version_constraint=version if version != "unknown" else None
            )

        # Package manager
        if (self.project_root / "poetry.lock").exists():
            self.fingerprint.package_manager = "poetry"
        elif (self.project_root / "Pipfile.lock").exists():
            self.fingerprint.package_manager = "pipenv"
        elif (self.project_root / "uv.lock").exists():
            self.fingerprint.package_manager = "uv"
        elif (self.project_root / "pyproject.toml").exists():
            self.fingerprint.package_manager = "pip"

    def _extract_from_requirements(self) -> None:
        """Extract Python dependencies from requirements.txt."""
        content = self._read_text("requirements.txt")
        if not content:
            return

        # Skip if already extracted from pyproject.toml
        if self.fingerprint.framework:
            return

        lines = content.splitlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Parse package==version or package>=version format
            match = re.match(r'^([a-zA-Z0-9_-]+)\s*([>=<~!]+)?\s*([0-9][^\s;#]*)?', line)
            if not match:
                continue

            pkg_name = match.group(1).lower()
            version = match.group(3) or "unknown"
            constraint = f"{match.group(2) or ''}{version}" if match.group(2) else version

            # Django
            if pkg_name == "django" and not self.fingerprint.framework:
                self.fingerprint.framework = VersionInfo(
                    name="django",
                    version=self._parse_version_constraint(version),
                    version_constraint=constraint
                )
                self.fingerprint.framework_type = "django"

            # FastAPI
            elif pkg_name == "fastapi" and not self.fingerprint.framework:
                self.fingerprint.framework = VersionInfo(
                    name="fastapi",
                    version=self._parse_version_constraint(version),
                    version_constraint=constraint
                )
                self.fingerprint.framework_type = "fastapi"

            # Flask
            elif pkg_name == "flask" and not self.fingerprint.framework:
                self.fingerprint.framework = VersionInfo(
                    name="flask",
                    version=self._parse_version_constraint(version),
                    version_constraint=constraint
                )
                self.fingerprint.framework_type = "flask"

            # pytest
            elif pkg_name == "pytest" and not self.fingerprint.test_framework:
                self.fingerprint.test_framework = VersionInfo(
                    name="pytest",
                    version=self._parse_version_constraint(version),
                    version_constraint=constraint
                )

        # Python version from runtime.txt (Heroku style)
        runtime = self._read_text("runtime.txt")
        if runtime and not self.fingerprint.python_version:
            py_match = re.search(r'python-(\d+\.\d+\.?\d*)', runtime, re.IGNORECASE)
            if py_match:
                self.fingerprint.python_version = VersionInfo(
                    name="python",
                    version=py_match.group(1)
                )

        if not self.fingerprint.package_manager:
            self.fingerprint.package_manager = "pip"

    def _extract_from_composer(self) -> None:
        """Extract PHP/Laravel versions from composer.json."""
        composer = self._read_json("composer.json")
        if not composer:
            return

        require = composer.get("require", {})
        require_dev = composer.get("require-dev", {})

        # PHP version
        if "php" in require:
            php_constraint = require["php"]
            # Parse version from constraint like ">=7.0.0" or "^8.1"
            version = self._parse_version_constraint(php_constraint)
            self.fingerprint.php_version = VersionInfo(
                name="php",
                version=version,
                version_constraint=php_constraint
            )

        # Laravel version
        if "laravel/framework" in require:
            laravel_constraint = require["laravel/framework"]
            version = self._parse_version_constraint(laravel_constraint)
            self.fingerprint.framework = VersionInfo(
                name="laravel",
                version=version,
                version_constraint=laravel_constraint
            )
            self.fingerprint.framework_type = "laravel"

        # Check for laravel-modules
        if "nwidart/laravel-modules" in require:
            self.fingerprint.module_system = "laravel-modules"

        # Key dependencies for code generation
        key_php_deps = [
            "guzzlehttp/guzzle",
            "phpunit/phpunit",
            "dompdf/dompdf",
            "phpoffice/phpspreadsheet",
            "spatie/laravel-permission",
            "laravel/sanctum",
            "laravel/passport",
            "sentry/sentry-laravel",
        ]

        for dep in key_php_deps:
            if dep in require:
                self.fingerprint.key_dependencies.append(VersionInfo(
                    name=dep,
                    version=self._parse_version_constraint(require[dep]),
                    version_constraint=require[dep]
                ))
            elif dep in require_dev:
                self.fingerprint.key_dependencies.append(VersionInfo(
                    name=dep,
                    version=self._parse_version_constraint(require_dev[dep]),
                    version_constraint=require_dev[dep]
                ))

        # Test framework
        if "phpunit/phpunit" in require_dev:
            self.fingerprint.test_framework = VersionInfo(
                name="phpunit",
                version=self._parse_version_constraint(require_dev["phpunit/phpunit"]),
                version_constraint=require_dev["phpunit/phpunit"]
            )
        elif "codeception/codeception" in require_dev:
            self.fingerprint.test_framework = VersionInfo(
                name="codeception",
                version=self._parse_version_constraint(require_dev["codeception/codeception"]),
                version_constraint=require_dev["codeception/codeception"]
            )

        # Database from dependencies
        db_drivers = {
            "jacquestvanzuydam/laravel-firebird": "firebird",
            "doctrine/dbal": "dbal",
            "mongodb/laravel-mongodb": "mongodb",
            "jenssegers/mongodb": "mongodb",
        }
        for driver, db_type in db_drivers.items():
            if driver in require:
                if not self.fingerprint.database:
                    self.fingerprint.database = DatabaseInfo(type=db_type, driver=driver)

        self.fingerprint.package_manager = "composer"

    def _extract_from_package_json(self) -> None:
        """Extract Node.js/npm versions from package.json."""
        package = self._read_json("package.json")
        if not package:
            return

        deps = package.get("dependencies", {})
        dev_deps = package.get("devDependencies", {})
        engines = package.get("engines", {})

        # Node version from engines
        if "node" in engines:
            node_constraint = engines["node"]
            self.fingerprint.node_version = VersionInfo(
                name="node",
                version=self._parse_version_constraint(node_constraint),
                version_constraint=node_constraint
            )

        # Check for .nvmrc
        nvmrc = self._read_text(".nvmrc")
        if nvmrc and not self.fingerprint.node_version:
            self.fingerprint.node_version = VersionInfo(
                name="node",
                version=nvmrc.strip()
            )

        # Build tools
        build_tools = {
            "laravel-mix": "laravel-mix",
            "vite": "vite",
            "webpack": "webpack",
            "esbuild": "esbuild",
            "parcel": "parcel",
        }
        for tool, tool_name in build_tools.items():
            if tool in deps or tool in dev_deps:
                version_str = deps.get(tool) or dev_deps.get(tool)
                self.fingerprint.build_tool = VersionInfo(
                    name=tool_name,
                    version=self._parse_version_constraint(version_str),
                    version_constraint=version_str
                )
                break

        # CSS frameworks
        css_frameworks = {
            "bootstrap": "bootstrap",
            "tailwindcss": "tailwind",
            "@tailwindcss/ui": "tailwind",
            "bulma": "bulma",
        }
        for pkg, framework in css_frameworks.items():
            if pkg in deps:
                self.fingerprint.css_framework = VersionInfo(
                    name=framework,
                    version=self._parse_version_constraint(deps[pkg]),
                    version_constraint=deps[pkg]
                )
                break

        # JS frameworks
        js_frameworks = {
            "vue": "vue",
            "react": "react",
            "jquery": "jquery",
            "angular": "angular",
            "@angular/core": "angular",
            "svelte": "svelte",
        }
        for pkg, framework in js_frameworks.items():
            if pkg in deps:
                self.fingerprint.js_framework = VersionInfo(
                    name=framework,
                    version=self._parse_version_constraint(deps[pkg]),
                    version_constraint=deps[pkg]
                )
                break

        # TypeScript
        if "typescript" in deps or "typescript" in dev_deps:
            self.fingerprint.has_typescript = True

        # Package manager detection
        if (self.project_root / "yarn.lock").exists():
            self.fingerprint.package_manager = "yarn"
        elif (self.project_root / "pnpm-lock.yaml").exists():
            self.fingerprint.package_manager = "pnpm"
        elif (self.project_root / "package-lock.json").exists():
            self.fingerprint.package_manager = "npm"

        # Key Node.js dependencies
        key_node_deps = [
            "axios", "moment", "lodash", "dayjs",
            "express", "fastify", "socket.io",
            "prisma", "sequelize", "typeorm",
        ]
        for dep in key_node_deps:
            if dep in deps:
                self.fingerprint.key_dependencies.append(VersionInfo(
                    name=dep,
                    version=self._parse_version_constraint(deps[dep]),
                    version_constraint=deps[dep]
                ))

    def _extract_from_env(self) -> None:
        """Extract database config from .env files."""
        env_files = [".env", ".env.example", ".env.local"]
        env_content = None

        for env_file in env_files:
            content = self._read_text(env_file)
            if content:
                env_content = content
                break

        if not env_content:
            return

        # Parse DB_CONNECTION
        db_match = re.search(r"DB_CONNECTION\s*=\s*(\w+)", env_content)
        if db_match and not self.fingerprint.database:
            db_type = db_match.group(1).lower()
            self.fingerprint.database = DatabaseInfo(type=db_type)

        # Parse DB_HOST for version hints (e.g., mysql:8.0)
        host_match = re.search(r"DB_HOST\s*=\s*([^\s\n]+)", env_content)
        if host_match and self.fingerprint.database:
            host = host_match.group(1)
            # Check if it's a docker service with version
            version_match = re.search(r":(\d+\.?\d*)", host)
            if version_match:
                self.fingerprint.database.version = version_match.group(1)

    def _extract_from_lockfiles(self) -> None:
        """Extract resolved versions from lock files."""
        # composer.lock for exact PHP package versions
        composer_lock = self._read_json("composer.lock")
        if composer_lock and self.fingerprint.framework:
            packages = composer_lock.get("packages", [])
            for pkg in packages:
                if pkg.get("name") == "laravel/framework":
                    self.fingerprint.framework.resolved_version = pkg.get("version")
                    break

        # package-lock.json for exact Node package versions
        package_lock = self._read_json("package-lock.json")
        if package_lock:
            packages = package_lock.get("packages", {})
            # Get node version from lockfile if available
            root_pkg = packages.get("", {})
            if "node" in root_pkg.get("engines", {}):
                pass  # Already extracted from package.json

    def _detect_features(self) -> None:
        """Detect additional project features."""
        # Docker
        docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
        for df in docker_files:
            if (self.project_root / df).exists():
                self.fingerprint.has_docker = True
                break

        # CI/CD
        ci_paths = [
            ".github/workflows",
            ".gitlab-ci.yml",
            ".circleci",
            "Jenkinsfile",
            ".travis.yml",
            "azure-pipelines.yml",
        ]
        for ci_path in ci_paths:
            if (self.project_root / ci_path).exists():
                self.fingerprint.has_ci = True
                break

    def _parse_version_constraint(self, constraint: str) -> str:
        """Parse a version number from a constraint string."""
        if not constraint:
            return "unknown"

        # Remove common prefixes
        cleaned = constraint.strip()

        # Handle exact versions
        if re.match(r"^\d+\.\d+", cleaned):
            return cleaned.split(",")[0].strip()

        # Handle constraints like ^5.6, ~5.6, >=7.0, etc.
        match = re.search(r"(\d+\.?\d*\.?\d*)", cleaned)
        if match:
            return match.group(1)

        return cleaned
