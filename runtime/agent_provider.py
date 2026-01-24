"""
ProcessOS Agent Provider

Sprint 3, Story S3-001: AgentProvider Abstraction + Anthropic Adapter
Sprint 3, Story S3-002: Agent Contract Validation integration
Provides abstract AgentProvider interface with Mock (default) and Anthropic implementations.
"""

import json
import os
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Lazy import for anthropic SDK (only when needed)
anthropic = None

__all__ = [
    "AgentProvider",
    "AgentResponse",
    "MockAgentProvider",
    "MockDelayProvider",
    "AnthropicAgentProvider",
    "ConfigurationError",
    "AgentOutputValidationError",
    "AgentTimeoutError",
    "get_provider",
]


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class AgentOutputValidationError(Exception):
    """Raised when agent output fails contract validation.

    Wraps the underlying ValidationError with agent context.

    Attributes:
        message: Human-readable error description
        step_id: ID of the step that produced invalid output (if known)
        agent_id: ID of the agent that produced invalid output (if known)
        original_error: The underlying ValidationError from ContractValidator
    """

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        self.step_id = step_id
        self.agent_id = agent_id
        self.original_error = original_error
        super().__init__(message)


class AgentTimeoutError(Exception):
    """Raised when agent invocation exceeds the configured timeout.

    Attributes:
        message: Human-readable error description
        timeout: The configured timeout in seconds
        elapsed: Actual elapsed time before timeout (if measurable)
    """

    def __init__(
        self,
        message: str,
        timeout: float,
        elapsed: Optional[float] = None
    ):
        self.timeout = timeout
        self.elapsed = elapsed
        super().__init__(message)


@dataclass
class AgentResponse:
    """Structured response from an agent invocation.

    Attributes:
        content: The agent's response text
        model: Model identifier (e.g., "claude-sonnet-4-20250514")
        usage: Token counts dict with 'input_tokens' and 'output_tokens'
    """
    content: str
    model: str
    usage: Dict[str, int]


class AgentProvider(ABC):
    """Abstract base class for agent providers.

    Defines the contract for invoking agents with prompts and context.
    Subclasses must implement the invoke() method.
    """

    # Lazy-loaded validator (shared across instances)
    _validator = None

    @abstractmethod
    def invoke(
        self,
        prompt: str,
        context: Dict[str, Any],
        timeout: float = 60.0
    ) -> AgentResponse:
        """Invoke the agent with a prompt and context.

        Args:
            prompt: The prompt text to send to the agent
            context: Additional context dict (step info, run state, etc.)
            timeout: Maximum time in seconds to wait for response (default: 60s)

        Returns:
            AgentResponse with content, model, and usage information

        Raises:
            AgentTimeoutError: If the invocation exceeds the timeout
        """
        pass

    def invoke_validated(
        self,
        prompt: str,
        context: Dict[str, Any],
        timeout: float = 60.0
    ) -> tuple[AgentResponse, Dict[str, Any]]:
        """Invoke agent and validate output against contract schema.

        Combines invoke() with output validation. The agent's response content
        is expected to be valid JSON matching the agent-output schema.

        Args:
            prompt: The prompt text to send to the agent
            context: Additional context dict (step info, run state, etc.)
            timeout: Maximum time in seconds to wait for response (default: 60s)

        Returns:
            Tuple of (AgentResponse, validated_output_dict)

        Raises:
            AgentOutputValidationError: If content is not valid JSON or fails schema
            AgentTimeoutError: If the invocation exceeds the timeout
        """
        response = self.invoke(prompt, context, timeout=timeout)
        validated = self.validate_output(response.content, context)
        return response, validated

    def validate_output(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate agent output content against contract schema.

        Args:
            content: Raw content string from agent (expected to be JSON)
            context: Optional context with step_id/agent_id for error messages

        Returns:
            Validated and parsed output dict

        Raises:
            AgentOutputValidationError: If content fails validation
        """
        # Get step/agent IDs from context for error messages
        step_id = context.get("step_id") if context else None
        agent_id = context.get("agent_id") if context else None

        # Parse JSON
        try:
            output = json.loads(content)
        except json.JSONDecodeError as e:
            raise AgentOutputValidationError(
                f"Agent output is not valid JSON: {e}",
                step_id=step_id,
                agent_id=agent_id,
                original_error=e
            )

        # Validate against schema
        # Import ValidationError locally to avoid circular imports at module load
        from contract_validator import ValidationError

        try:
            validator = self._get_validator()
            validated = validator.validate(output)
            return validated
        except ValidationError as e:
            raise AgentOutputValidationError(
                f"Agent output validation failed: {e}",
                step_id=step_id,
                agent_id=agent_id,
                original_error=e
            )

    @classmethod
    def _get_validator(cls):
        """Get or create the shared ContractValidator instance."""
        if cls._validator is None:
            from contract_validator import ContractValidator
            cls._validator = ContractValidator()
        return cls._validator


class MockAgentProvider(AgentProvider):
    """Mock agent provider for testing.

    Returns a pre-configured canned response for any invocation.
    Deterministic and immediate - no network calls.
    """

    def __init__(self, response: Optional[AgentResponse] = None):
        """Initialize with a canned response.

        Args:
            response: The AgentResponse to return for all invocations.
                     Defaults to a simple "Mock response" if not provided.
        """
        if response is None:
            response = AgentResponse(
                content="Mock response",
                model="mock-model",
                usage={"input_tokens": 0, "output_tokens": 0}
            )
        self._response = response

    def invoke(
        self,
        prompt: str,
        context: Dict[str, Any],
        timeout: float = 60.0
    ) -> AgentResponse:
        """Return the configured canned response immediately.

        Args:
            prompt: Ignored - returns canned response regardless
            context: Ignored - returns canned response regardless
            timeout: Ignored - mock returns immediately

        Returns:
            A copy of the pre-configured AgentResponse (prevents mutation issues)
        """
        return deepcopy(self._response)


class MockDelayProvider(AgentProvider):
    """Mock agent provider that simulates network delay for timeout testing.

    Returns a canned response after a configurable delay.
    If the timeout is exceeded, raises AgentTimeoutError.
    """

    def __init__(
        self,
        delay_seconds: float = 0.0,
        response: Optional[AgentResponse] = None
    ):
        """Initialize with delay and optional canned response.

        Args:
            delay_seconds: Time to wait before returning response
            response: The AgentResponse to return (default: simple mock response)
        """
        self.delay_seconds = delay_seconds
        if response is None:
            response = AgentResponse(
                content='{"decision": "proceed", "reasoning": "Delayed response"}',
                model="mock-delay",
                usage={"input_tokens": 0, "output_tokens": 0}
            )
        self._response = response

    def invoke(
        self,
        prompt: str,
        context: Dict[str, Any],
        timeout: float = 60.0
    ) -> AgentResponse:
        """Return response after delay, or timeout.

        Args:
            prompt: Ignored
            context: Ignored
            timeout: If delay exceeds this, raises AgentTimeoutError

        Returns:
            AgentResponse after delay

        Raises:
            AgentTimeoutError: If delay_seconds > timeout
        """
        import time

        time.time()

        if self.delay_seconds > timeout:
            # Simulate timeout - don't actually wait, just fail
            raise AgentTimeoutError(
                f"Agent call timed out after {timeout}s",
                timeout=timeout,
                elapsed=timeout
            )

        # Simulate delay (for fast tests, skip actual sleep if delay is small)
        if self.delay_seconds > 0.01:
            time.sleep(min(self.delay_seconds, timeout))

        return deepcopy(self._response)


class AnthropicAgentProvider(AgentProvider):
    """Anthropic Claude agent provider.

    Requires PROCESSOS_LLM_ENABLED=true environment variable.
    Uses the anthropic SDK to make real API calls.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 60.0
    ):
        """Initialize the Anthropic provider.

        Args:
            model: The Claude model to use (default: claude-sonnet-4-20250514)
            timeout: Default timeout in seconds for API calls (default: 60s)

        Raises:
            ConfigurationError: If PROCESSOS_LLM_ENABLED is not 'true'
        """
        # Check flag first
        llm_enabled = os.environ.get("PROCESSOS_LLM_ENABLED", "").lower()
        if llm_enabled != "true":
            raise ConfigurationError(
                "PROCESSOS_LLM_ENABLED must be set to 'true' to use AnthropicAgentProvider. "
                "This prevents accidental API costs in tests."
            )

        # Check API key is available
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ConfigurationError(
                "ANTHROPIC_API_KEY environment variable must be set to use AnthropicAgentProvider."
            )

        # Import anthropic SDK and httpx lazily
        global anthropic
        if anthropic is None:
            import anthropic as _anthropic
            anthropic = _anthropic

        import httpx

        self.model = model
        self.timeout = timeout

        # Configure SDK-level timeout via httpx.Timeout
        sdk_timeout = httpx.Timeout(
            connect=10.0,       # Connection timeout
            read=timeout,       # Read timeout (main constraint)
            write=10.0,         # Write timeout
            pool=10.0           # Pool timeout
        )
        self.client = anthropic.Anthropic(timeout=sdk_timeout)

    def invoke(
        self,
        prompt: str,
        context: Dict[str, Any],
        timeout: float = 60.0
    ) -> AgentResponse:
        """Invoke Claude API with the prompt.

        Args:
            prompt: The prompt text to send to Claude
            context: Additional context (currently unused, reserved for future)
            timeout: Accepted for interface consistency but not used.
                    AnthropicAgentProvider uses the timeout set at construction
                    (SDK limitation - timeout is configured on the httpx client).

        Returns:
            AgentResponse with Claude's response and token usage

        Raises:
            AgentTimeoutError: If the API call exceeds the instance timeout
        """
        import time
        import httpx

        start_time = time.time()

        # Note: Per-call timeout parameter is accepted for interface consistency
        # but AnthropicAgentProvider uses instance timeout (SDK limitation).
        # The timeout is configured at client creation time via httpx.Timeout.

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
        except (httpx.TimeoutException, anthropic.APITimeoutError) as e:
            elapsed = time.time() - start_time
            raise AgentTimeoutError(
                f"Agent call timed out after {self.timeout}s",
                timeout=self.timeout,
                elapsed=elapsed
            ) from e

        # Extract text content from response
        content = ""
        for block in message.content:
            if hasattr(block, "text"):
                content += block.text

        return AgentResponse(
            content=content,
            model=message.model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        )


def get_provider(use_real_llm: Optional[bool] = None) -> AgentProvider:
    """Factory function to get the appropriate agent provider.

    Returns MockAgentProvider by default. Returns AnthropicAgentProvider
    only when PROCESSOS_LLM_ENABLED=true.

    Args:
        use_real_llm: Explicit override. If True and PROCESSOS_LLM_ENABLED=true,
                     returns AnthropicAgentProvider. If False, always returns Mock.
                     If None (default), uses environment variable.

    Returns:
        AgentProvider instance (Mock or Anthropic)

    Note:
        AnthropicAgentProvider always requires PROCESSOS_LLM_ENABLED=true
        to prevent accidental API costs. The use_real_llm parameter cannot
        bypass this requirement.
    """
    llm_enabled = os.environ.get("PROCESSOS_LLM_ENABLED", "").lower() == "true"

    # Explicit False always returns Mock
    if use_real_llm is False:
        return MockAgentProvider()

    # Only use real LLM if flag is set (use_real_llm=True or None with flag)
    if llm_enabled and use_real_llm is not False:
        return AnthropicAgentProvider()
    else:
        return MockAgentProvider()
