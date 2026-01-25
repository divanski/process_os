"""
ProcessOS LLM Types

Data types for LLM responses and usage tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class LLMUsage:
    """
    Token usage information from LLM response.

    Attributes:
        input_tokens: Number of tokens in the prompt
        output_tokens: Number of tokens in the response
        total_tokens: Total tokens used (input + output)
    """

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """
    Response from LLM API call.

    Attributes:
        content: The response text content
        usage: Token usage information
        model: The model that generated the response
        latency: Response time in seconds
        request_id: Optional request ID for tracking
        created_at: When the response was created
        metadata: Additional metadata from the API
    """

    content: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = ""
    latency: float = 0.0
    request_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
            "model": self.model,
            "latency": self.latency,
            "request_id": self.request_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMResponse":
        """Create from dictionary."""
        usage_data = data.get("usage", {})
        usage = LLMUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            content=data.get("content", ""),
            usage=usage,
            model=data.get("model", ""),
            latency=data.get("latency", 0.0),
            request_id=data.get("request_id"),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class DetectionSignal:
    """
    Single signal evaluated during architecture detection.

    Signals are individual indicators of language, framework, patterns, or conventions.
    Each signal contributes a confidence score to overall analysis.
    """

    signal_type: str  # file_extension, import_analysis, framework_markers, convention_analysis
    signal_name: str
    confidence: float  # [0.0, 1.0]
    evidence: List[str] = field(default_factory=list)  # Evidence supporting this signal

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "signal_type": self.signal_type,
            "signal_name": self.signal_name,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class ConventionProfile:
    """
    Learned conventions from project analysis.

    Contains naming styles, directory structures, documentation patterns, etc.
    discovered during architecture analysis.
    """

    language: str
    framework: str

    # Naming conventions
    class_naming_style: Optional[str] = None  # PascalCase, snake_case, etc.
    method_naming_style: Optional[str] = None
    variable_naming_style: Optional[str] = None

    # Directory structure conventions
    namespace_pattern: Optional[str] = None  # e.g., App\Services\{Domain}
    directory_structure: Optional[str] = None

    # Documentation patterns
    documentation_style: Optional[str] = None

    # Additional discovered conventions
    additional_conventions: Dict[str, Any] = field(default_factory=dict)

    # Confidence in the convention profile
    overall_confidence: float = 0.0  # [0.0, 1.0]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "framework": self.framework,
            "class_naming_style": self.class_naming_style,
            "method_naming_style": self.method_naming_style,
            "variable_naming_style": self.variable_naming_style,
            "namespace_pattern": self.namespace_pattern,
            "directory_structure": self.directory_structure,
            "documentation_style": self.documentation_style,
            "additional_conventions": self.additional_conventions,
            "overall_confidence": self.overall_confidence,
        }


@dataclass
class ArchitectureAnalysis:
    """
    Record of a single architecture detection run.

    Contains all signals, patterns, and conventions detected from a project,
    along with confidence scores and metadata.
    """

    analysis_id: str  # UUID
    session_id: str  # UUID
    timestamp: datetime
    project_id: str  # Hash of project path

    # Detection results
    detected_language: str
    detected_framework: str
    overall_confidence: float  # [0.0, 1.0], must be ≥0.90 for code generation

    # Analysis details
    signals_used: List[DetectionSignal] = field(default_factory=list)
    patterns_discovered: List[Dict[str, Any]] = field(default_factory=list)
    conventions_learned: Optional[ConventionProfile] = None

    # Metadata
    files_scanned: int = 0
    files_analyzed: int = 0
    analysis_duration_seconds: float = 0.0
    project_size_mb: float = 0.0
    language_breakdown: Dict[str, int] = field(default_factory=dict)
    framework_marker_strength: str = "weak"  # weak | moderate | strong

    # User information
    user_id: str = ""

    # Approval status
    approval_status: str = "pending"  # pending | approved | rejected
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "analysis_id": self.analysis_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "project_id": self.project_id,
            "detected_language": self.detected_language,
            "detected_framework": self.detected_framework,
            "overall_confidence": self.overall_confidence,
            "signals_used": [s.to_dict() for s in self.signals_used],
            "patterns_discovered": self.patterns_discovered,
            "conventions_learned": self.conventions_learned.to_dict()
            if self.conventions_learned
            else None,
            "files_scanned": self.files_scanned,
            "files_analyzed": self.files_analyzed,
            "analysis_duration_seconds": self.analysis_duration_seconds,
            "project_size_mb": self.project_size_mb,
            "language_breakdown": self.language_breakdown,
            "framework_marker_strength": self.framework_marker_strength,
            "user_id": self.user_id,
            "approval_status": self.approval_status,
            "rejection_reason": self.rejection_reason,
        }
