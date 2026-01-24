"""
ProcessOS LLM Configuration

Configuration dataclass for LLM client settings.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """
    Configuration for LLM client.

    Attributes:
        model: The model to use (e.g., "claude-sonnet-4-20250514")
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0.0-1.0)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds
        api_key_env: Environment variable name for API key
    """

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout: float = 60.0
    max_retries: int = 3
    retry_delay: float = 1.0
    api_key_env: str = "ANTHROPIC_API_KEY"

    # Optional overrides
    api_base_url: Optional[str] = None
    extra_headers: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration values."""
        if self.temperature < 0.0 or self.temperature > 1.0:
            raise ValueError(f"Temperature must be between 0.0 and 1.0, got {self.temperature}")

        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")

        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")

        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")


# Default configuration
DEFAULT_CONFIG = LLMConfig()
