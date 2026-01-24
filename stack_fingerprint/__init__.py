"""
ProcessOS Stack Fingerprint Module

Evidence-based detection of project technology stacks.
"""

from .detector import (
    DetectedFramework,
    DetectedStack,
    DetectionResult,
    StackDetector,
)
from .fingerprint import (
    FingerprintGenerator,
    StackFingerprint,
    generate_fingerprint,
)
from .markers import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    FRAMEWORK_MARKERS,
    SKIP_DIRECTORIES,
    STACK_MARKERS,
    FrameworkMarker,
    StackMarker,
    get_framework_markers_for_stack,
    get_stack_marker,
)
from .version_extractor import (
    DatabaseInfo,
    DetailedFingerprint,
    VersionExtractor,
    VersionInfo,
)

__all__ = [
    # Detector
    "StackDetector",
    "DetectedStack",
    "DetectedFramework",
    "DetectionResult",
    # Fingerprint
    "FingerprintGenerator",
    "StackFingerprint",
    "generate_fingerprint",
    # Version Extractor
    "VersionExtractor",
    "DetailedFingerprint",
    "VersionInfo",
    "DatabaseInfo",
    # Markers
    "STACK_MARKERS",
    "FRAMEWORK_MARKERS",
    "SKIP_DIRECTORIES",
    "StackMarker",
    "FrameworkMarker",
    "get_stack_marker",
    "get_framework_markers_for_stack",
    # Confidence constants
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_LOW",
]
