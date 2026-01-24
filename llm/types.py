"""
ProcessOS LLM Types

Data types for LLM responses and usage tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


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
