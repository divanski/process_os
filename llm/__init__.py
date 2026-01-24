"""
ProcessOS LLM Module

Provides LLM client integration with Anthropic Claude API.

Usage:
    from process_os.llm import get_llm_client, LLMConfig

    # Use default configuration
    client = get_llm_client()
    response = client.complete(system_prompt, user_prompt)

    # Use custom configuration
    config = LLMConfig(model="claude-sonnet-4-20250514", max_tokens=8192)
    client = get_llm_client(config=config)

    # Get JSON response
    data = client.complete_json(system_prompt, user_prompt)
"""

from .config import LLMConfig, DEFAULT_CONFIG
from .types import LLMResponse, LLMUsage
from .client import AnthropicClient, get_llm_client


# Error types
class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, cause: Exception = None):
        super().__init__(message)
        self.cause = cause


class RateLimitError(LLMError):
    """Raised when API rate limit is exceeded."""

    pass


class AuthenticationError(LLMError):
    """Raised when API authentication fails."""

    pass


class TimeoutError(LLMError):
    """Raised when API request times out."""

    pass


__all__ = [
    # Config
    "LLMConfig",
    "DEFAULT_CONFIG",
    # Types
    "LLMResponse",
    "LLMUsage",
    # Client
    "AnthropicClient",
    "get_llm_client",
    # Errors
    "LLMError",
    "RateLimitError",
    "AuthenticationError",
    "TimeoutError",
]
