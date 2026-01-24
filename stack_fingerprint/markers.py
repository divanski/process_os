"""
ProcessOS Stack Fingerprint Markers

Defines marker files for detecting technology stacks with confidence scoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Confidence level constants
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


@dataclass
class StackMarker:
    """
    Definition of a technology stack's detection markers.

    Supports multi-signal confidence scoring for more accurate detection.
    """

    stack_id: str
    display_name: str
    markers: List[str]  # File patterns to detect
    high_confidence: List[str] = field(default_factory=list)  # Strong indicators
    version_files: List[str] = field(default_factory=list)  # Files with version info

    # Enhanced confidence scoring (v0.8.0+)
    primary_files: List[str] = field(default_factory=list)  # Files that must exist
    secondary_files: List[str] = field(default_factory=list)  # Files that boost confidence
    file_patterns: List[str] = field(default_factory=list)  # Glob patterns to search
    content_patterns: Dict[str, str] = field(default_factory=dict)  # file -> regex patterns
    base_confidence: str = CONFIDENCE_MEDIUM  # Starting confidence if primary_files match
    confidence_boost: float = 0.2  # Added per secondary signal (max 1.0)

    def __post_init__(self):
        """Initialize primary_files from markers if not set."""
        if not self.primary_files and self.markers:
            self.primary_files = list(self.markers)
        if not self.secondary_files and self.high_confidence:
            self.secondary_files = list(self.high_confidence)


@dataclass
class FrameworkMarker:
    """
    Definition of a framework's detection markers.

    Supports multi-signal confidence scoring for accurate framework detection.
    """

    framework_id: str
    display_name: str
    stack: str  # Parent stack
    dependency_names: List[str]  # Names to look for in dependency files

    # Enhanced detection (v0.8.0+)
    primary_files: List[str] = field(default_factory=list)  # Files that must exist
    secondary_files: List[str] = field(default_factory=list)  # Files that boost confidence
    file_patterns: List[str] = field(default_factory=list)  # Glob patterns to search
    content_patterns: Dict[str, str] = field(default_factory=dict)  # file -> regex patterns
    base_confidence: str = CONFIDENCE_MEDIUM
    confidence_boost: float = 0.2


# Stack markers - ordered by detection priority
STACK_MARKERS: List[StackMarker] = [
    StackMarker(
        stack_id="python",
        display_name="Python",
        markers=["pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "setup.cfg"],
        high_confidence=["pyproject.toml", "setup.py"],
        version_files=["pyproject.toml", ".python-version"],
    ),
    StackMarker(
        stack_id="node",
        display_name="Node.js",
        markers=["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        high_confidence=["package.json"],
        version_files=["package.json", ".nvmrc", ".node-version"],
    ),
    StackMarker(
        stack_id="rust",
        display_name="Rust",
        markers=["Cargo.toml", "Cargo.lock"],
        high_confidence=["Cargo.toml"],
        version_files=["Cargo.toml", "rust-toolchain.toml"],
    ),
    StackMarker(
        stack_id="go",
        display_name="Go",
        markers=["go.mod", "go.sum"],
        high_confidence=["go.mod"],
        version_files=["go.mod"],
    ),
    StackMarker(
        stack_id="java",
        display_name="Java",
        markers=["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
        high_confidence=["pom.xml", "build.gradle"],
        version_files=["pom.xml", "build.gradle", ".java-version"],
    ),
    StackMarker(
        stack_id="dotnet",
        display_name=".NET",
        markers=["*.csproj", "*.fsproj", "*.sln", "global.json"],
        high_confidence=["*.csproj", "*.sln"],
        version_files=["global.json"],
    ),
    StackMarker(
        stack_id="ruby",
        display_name="Ruby",
        markers=["Gemfile", "Gemfile.lock", "*.gemspec"],
        high_confidence=["Gemfile"],
        version_files=["Gemfile", ".ruby-version"],
    ),
    StackMarker(
        stack_id="php",
        display_name="PHP",
        markers=["composer.json", "composer.lock"],
        high_confidence=["composer.json"],
        version_files=["composer.json"],
    ),
]

# Framework markers - for deeper detection with confidence scoring
FRAMEWORK_MARKERS: List[FrameworkMarker] = [
    # ===================
    # PHP Frameworks
    # ===================
    # T011: Laravel marker with confidence scoring
    FrameworkMarker(
        framework_id="laravel",
        display_name="Laravel",
        stack="php",
        dependency_names=["laravel/framework"],
        primary_files=["artisan", "composer.json"],
        secondary_files=[
            "app/Http/Kernel.php",
            "routes/web.php",
            "routes/api.php",
            "config/app.php",
            "bootstrap/app.php",
        ],
        file_patterns=["app/**/*.php", "routes/*.php"],
        content_patterns={
            "composer.json": r'"laravel/framework"',
            "artisan": r"Laravel",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.15,
    ),

    # ===================
    # Python Frameworks
    # ===================
    # T012: Django marker with confidence scoring
    FrameworkMarker(
        framework_id="django",
        display_name="Django",
        stack="python",
        dependency_names=["django", "Django"],
        primary_files=["manage.py"],
        secondary_files=[
            "settings.py",
            "urls.py",
            "wsgi.py",
            "asgi.py",
        ],
        file_patterns=["**/settings.py", "**/urls.py", "**/models.py"],
        content_patterns={
            "manage.py": r"django",
            "settings.py": r"INSTALLED_APPS",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
    # T016: FastAPI marker with confidence scoring
    FrameworkMarker(
        framework_id="fastapi",
        display_name="FastAPI",
        stack="python",
        dependency_names=["fastapi"],
        primary_files=["main.py"],
        secondary_files=[
            "app/main.py",
            "api/main.py",
            "routers/",
        ],
        file_patterns=["**/*.py"],
        content_patterns={
            "main.py": r"from fastapi import|FastAPI\(\)",
            "requirements.txt": r"fastapi",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
    # T017: Flask marker with confidence scoring
    FrameworkMarker(
        framework_id="flask",
        display_name="Flask",
        stack="python",
        dependency_names=["flask", "Flask"],
        primary_files=["app.py"],
        secondary_files=[
            "wsgi.py",
            "application.py",
            "templates/",
            "static/",
        ],
        file_patterns=["**/*.py"],
        content_patterns={
            "app.py": r"from flask import|Flask\(__name__\)",
            "requirements.txt": r"flask|Flask",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
    FrameworkMarker(
        framework_id="pytest",
        display_name="pytest",
        stack="python",
        dependency_names=["pytest"],
        primary_files=["pytest.ini", "conftest.py"],
        secondary_files=["tests/", "test_*.py"],
        base_confidence=CONFIDENCE_LOW,
        confidence_boost=0.15,
    ),

    # ===================
    # Node.js Frameworks
    # ===================
    # T013: Express marker with confidence scoring
    FrameworkMarker(
        framework_id="express",
        display_name="Express",
        stack="node",
        dependency_names=["express"],
        primary_files=["package.json"],
        secondary_files=[
            "app.js",
            "server.js",
            "index.js",
            "routes/",
            "middleware/",
        ],
        file_patterns=["**/*.js", "**/*.ts"],
        content_patterns={
            "package.json": r'"express"',
            "app.js": r"require\(['\"]express['\"]\)|from ['\"]express['\"]",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
    # T018: Next.js marker with confidence scoring
    FrameworkMarker(
        framework_id="nextjs",
        display_name="Next.js",
        stack="node",
        dependency_names=["next"],
        primary_files=["package.json", "next.config.js"],
        secondary_files=[
            "next.config.mjs",
            "next.config.ts",
            "pages/",
            "app/",
            "public/",
        ],
        file_patterns=["pages/**/*.{js,jsx,ts,tsx}", "app/**/*.{js,jsx,ts,tsx}"],
        content_patterns={
            "package.json": r'"next"',
            "next.config.js": r"module\.exports|nextConfig",
        },
        base_confidence=CONFIDENCE_HIGH,
        confidence_boost=0.1,
    ),
    FrameworkMarker(
        framework_id="react",
        display_name="React",
        stack="node",
        dependency_names=["react"],
        primary_files=["package.json"],
        secondary_files=[
            "src/App.jsx",
            "src/App.tsx",
            "src/index.jsx",
            "src/index.tsx",
        ],
        content_patterns={
            "package.json": r'"react"',
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
    FrameworkMarker(
        framework_id="vue",
        display_name="Vue.js",
        stack="node",
        dependency_names=["vue"],
        primary_files=["package.json"],
        secondary_files=[
            "vue.config.js",
            "src/App.vue",
            "src/main.js",
            "src/main.ts",
        ],
        content_patterns={
            "package.json": r'"vue"',
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),

    # ===================
    # Ruby Frameworks
    # ===================
    # T014: Rails marker with confidence scoring
    FrameworkMarker(
        framework_id="rails",
        display_name="Ruby on Rails",
        stack="ruby",
        dependency_names=["rails"],
        primary_files=["Gemfile", "config/routes.rb"],
        secondary_files=[
            "config/application.rb",
            "config/environment.rb",
            "app/controllers/application_controller.rb",
            "app/models/application_record.rb",
            "bin/rails",
        ],
        file_patterns=["app/**/*.rb", "config/**/*.rb"],
        content_patterns={
            "Gemfile": r"gem ['\"]rails['\"]",
            "config/application.rb": r"Rails::Application",
        },
        base_confidence=CONFIDENCE_HIGH,
        confidence_boost=0.1,
    ),

    # ===================
    # Java Frameworks
    # ===================
    # T015: Spring Boot marker with confidence scoring
    FrameworkMarker(
        framework_id="spring-boot",
        display_name="Spring Boot",
        stack="java",
        dependency_names=["spring-boot-starter"],
        primary_files=["pom.xml"],
        secondary_files=[
            "build.gradle",
            "src/main/java/",
            "src/main/resources/application.properties",
            "src/main/resources/application.yml",
        ],
        file_patterns=["src/**/*.java"],
        content_patterns={
            "pom.xml": r"spring-boot-starter",
            "build.gradle": r"org\.springframework\.boot",
        },
        base_confidence=CONFIDENCE_MEDIUM,
        confidence_boost=0.2,
    ),
]


def get_stack_marker(stack_id: str) -> StackMarker | None:
    """Get marker definition for a stack."""
    for marker in STACK_MARKERS:
        if marker.stack_id == stack_id:
            return marker
    return None


def get_framework_markers_for_stack(stack_id: str) -> List[FrameworkMarker]:
    """Get framework markers for a given stack."""
    return [fm for fm in FRAMEWORK_MARKERS if fm.stack == stack_id]


# Directories to skip during scanning
SKIP_DIRECTORIES = {
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "vendor",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "target",  # Rust
    "build",
    "dist",
    ".next",
    ".nuxt",
}
