"""
ProcessOS Anthropic LLM Client

Client for Anthropic Claude API with retry logic, rate limiting, and telemetry.
"""

import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .config import LLMConfig, DEFAULT_CONFIG
from .types import LLMResponse, LLMUsage

if TYPE_CHECKING:
    from ..credentials import CredentialProvider


class AnthropicClient:
    """
    Client for Anthropic Claude API.

    Features:
    - Credential loading via CredentialProvider
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Usage tracking for cost estimation
    - Telemetry integration
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        credential_provider: Optional["CredentialProvider"] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the Anthropic client.

        Args:
            config: LLM configuration (uses DEFAULT_CONFIG if not provided)
            credential_provider: Provider for API key lookup
            api_key: Direct API key (overrides credential_provider)
        """
        self.config = config or DEFAULT_CONFIG
        self._credential_provider = credential_provider
        self._api_key = api_key
        self._client = None
        self._total_usage = LLMUsage()

        # Event callbacks
        self._on_request_started: Optional[Callable] = None
        self._on_request_completed: Optional[Callable] = None
        self._on_request_failed: Optional[Callable] = None

    def _get_api_key(self) -> str:
        """
        Get API key from available sources.

        Priority:
        1. Direct api_key parameter
        2. CredentialProvider
        3. Environment variable (fallback)

        Returns:
            API key string

        Raises:
            AuthenticationError: If no API key found
        """
        from . import AuthenticationError

        # Direct API key
        if self._api_key:
            return self._api_key

        # CredentialProvider
        if self._credential_provider:
            credential = self._credential_provider.get(self.config.api_key_env)
            if credential:
                return credential.value

        # Fallback: create default provider
        from ..credentials import CredentialProvider
        provider = CredentialProvider()
        credential = provider.get(self.config.api_key_env)
        if credential:
            return credential.value

        raise AuthenticationError(
            f"No API key found. Set {self.config.api_key_env} environment variable "
            "or provide api_key parameter."
        )

    def _get_client(self):
        """
        Get or create the Anthropic client instance.

        Returns:
            anthropic.Anthropic client instance

        Raises:
            LLMError: If anthropic package not installed
        """
        from . import LLMError

        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise LLMError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )

            api_key = self._get_api_key()

            client_kwargs = {
                "api_key": api_key,
                "timeout": self.config.timeout,
            }

            if self.config.api_base_url:
                client_kwargs["base_url"] = self.config.api_base_url

            if self.config.extra_headers:
                client_kwargs["default_headers"] = self.config.extra_headers

            self._client = anthropic.Anthropic(**client_kwargs)

        return self._client

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Make a completion request to the LLM.

        Args:
            system_prompt: System prompt for context
            user_prompt: User prompt with the actual request
            max_tokens: Override max tokens (uses config default if not provided)
            temperature: Override temperature (uses config default if not provided)

        Returns:
            LLMResponse with content and usage

        Raises:
            LLMError: On API errors
            RateLimitError: On rate limiting
            AuthenticationError: On auth failures
        """
        from . import LLMError, RateLimitError

        start_time = time.time()
        last_error = None

        # Emit request started event
        if self._on_request_started:
            self._on_request_started(system_prompt, user_prompt)

        for attempt in range(self.config.max_retries + 1):
            try:
                client = self._get_client()

                response = client.messages.create(
                    model=self.config.model,
                    max_tokens=max_tokens or self.config.max_tokens,
                    temperature=temperature if temperature is not None else self.config.temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                )

                latency = time.time() - start_time

                # Extract content
                content = ""
                if response.content:
                    content = response.content[0].text

                # Build usage
                usage = LLMUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                # Track total usage
                self._total_usage.input_tokens += usage.input_tokens
                self._total_usage.output_tokens += usage.output_tokens

                result = LLMResponse(
                    content=content,
                    usage=usage,
                    model=response.model,
                    latency=latency,
                    request_id=response.id if hasattr(response, 'id') else None,
                    created_at=datetime.now(),
                )

                # Emit completed event
                if self._on_request_completed:
                    self._on_request_completed(result)

                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Check for rate limiting
                if "rate" in str(e).lower() or error_type == "RateLimitError":
                    if attempt < self.config.max_retries:
                        # Exponential backoff
                        delay = self.config.retry_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                    raise RateLimitError(f"Rate limited after {self.config.max_retries + 1} attempts: {e}")

                # Check for authentication errors
                if "auth" in str(e).lower() or "api_key" in str(e).lower() or error_type == "AuthenticationError":
                    from . import AuthenticationError
                    raise AuthenticationError(f"Authentication failed: {e}")

                # Other errors - retry with backoff
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue

                # Emit failed event
                if self._on_request_failed:
                    self._on_request_failed(e)

                raise LLMError(f"LLM request failed after {self.config.max_retries + 1} attempts: {e}")

        # Should never reach here, but just in case
        raise LLMError(f"LLM request failed: {last_error}")

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Make a completion request expecting JSON response.

        Parses the response as JSON and returns the parsed object.

        Args:
            system_prompt: System prompt for context
            user_prompt: User prompt with the actual request
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            Parsed JSON response as dict

        Raises:
            LLMError: If response is not valid JSON
        """
        from . import LLMError
        import re

        response = self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content = response.content.strip()

        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        brace_match = re.search(r"\{[\s\S]*\}", content)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        raise LLMError(f"Could not parse JSON from LLM response: {content[:200]}...")

    @property
    def total_usage(self) -> LLMUsage:
        """Get total token usage across all requests."""
        return self._total_usage

    def reset_usage(self) -> None:
        """Reset usage tracking."""
        self._total_usage = LLMUsage()

    # Telemetry event registration

    def on_request_started(self, callback: Callable) -> None:
        """Register callback for request started events."""
        self._on_request_started = callback

    def on_request_completed(self, callback: Callable) -> None:
        """Register callback for request completed events."""
        self._on_request_completed = callback

    def on_request_failed(self, callback: Callable) -> None:
        """Register callback for request failed events."""
        self._on_request_failed = callback


# Singleton instance for convenience
_default_client: Optional[AnthropicClient] = None


def get_llm_client(
    config: Optional[LLMConfig] = None,
    credential_provider: Optional["CredentialProvider"] = None,
) -> AnthropicClient:
    """
    Get or create the default LLM client.

    Args:
        config: Optional configuration (uses DEFAULT_CONFIG if not provided)
        credential_provider: Optional credential provider

    Returns:
        AnthropicClient instance
    """
    global _default_client

    if _default_client is None or config is not None or credential_provider is not None:
        _default_client = AnthropicClient(
            config=config,
            credential_provider=credential_provider,
        )

    return _default_client
