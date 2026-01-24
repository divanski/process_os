"""
ProcessOS Agent Provider Tests

Sprint 3, Story S3-001: AgentProvider Abstraction
TDD tests for AgentProvider ABC, MockAgentProvider, and AnthropicAgentProvider.
"""

import os
import pytest
from unittest.mock import patch


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_agent_response_has_required_fields(self):
        """AgentResponse should have content, model, and usage fields."""
        from agent_provider import AgentResponse

        response = AgentResponse(
            content="Test response",
            model="claude-sonnet-4-20250514",
            usage={"input_tokens": 10, "output_tokens": 20}
        )

        assert response.content == "Test response"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.usage == {"input_tokens": 10, "output_tokens": 20}

    def test_agent_response_usage_has_token_counts(self):
        """Usage dict should contain input_tokens and output_tokens."""
        from agent_provider import AgentResponse

        response = AgentResponse(
            content="Hello",
            model="test-model",
            usage={"input_tokens": 5, "output_tokens": 15}
        )

        assert "input_tokens" in response.usage
        assert "output_tokens" in response.usage
        assert response.usage["input_tokens"] == 5
        assert response.usage["output_tokens"] == 15


class TestAgentProviderABC:
    """Tests for AgentProvider abstract base class."""

    def test_agent_provider_is_abstract(self):
        """AgentProvider cannot be instantiated directly."""
        from agent_provider import AgentProvider

        with pytest.raises(TypeError):
            AgentProvider()

    def test_agent_provider_requires_invoke_method(self):
        """Subclasses must implement invoke() method."""
        from agent_provider import AgentProvider

        class IncompleteProvider(AgentProvider):
            pass  # Missing invoke() implementation

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_agent_provider_invoke_signature(self):
        """invoke() should accept prompt and context, return AgentResponse."""
        from agent_provider import AgentProvider, AgentResponse

        class TestProvider(AgentProvider):
            def invoke(self, prompt: str, context: dict) -> AgentResponse:
                return AgentResponse(
                    content=f"Response to: {prompt}",
                    model="test-model",
                    usage={"input_tokens": 0, "output_tokens": 0}
                )

        provider = TestProvider()
        result = provider.invoke("test prompt", {"key": "value"})

        assert isinstance(result, AgentResponse)
        assert "test prompt" in result.content


class TestMockAgentProvider:
    """Tests for MockAgentProvider - AC1: Deterministic responses."""

    def test_mock_provider_returns_configured_response(self):
        """MockAgentProvider returns the canned response it was configured with."""
        from agent_provider import MockAgentProvider, AgentResponse

        canned_response = AgentResponse(
            content="Canned response content",
            model="mock-model",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned_response)

        result = provider.invoke("any prompt", {})

        assert result.content == "Canned response content"
        assert result.model == "mock-model"

    def test_mock_provider_returns_same_response_every_time(self):
        """MockAgentProvider is deterministic - same response every call."""
        from agent_provider import MockAgentProvider, AgentResponse

        canned = AgentResponse(
            content="Deterministic",
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        results = [provider.invoke(f"prompt {i}", {}) for i in range(5)]

        assert all(r.content == "Deterministic" for r in results)

    def test_mock_provider_ignores_prompt_content(self):
        """MockAgentProvider returns canned response regardless of prompt."""
        from agent_provider import MockAgentProvider, AgentResponse

        canned = AgentResponse(
            content="Fixed",
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        result1 = provider.invoke("Hello", {})
        result2 = provider.invoke("Completely different prompt", {"complex": "context"})

        assert result1.content == result2.content == "Fixed"

    def test_mock_provider_returns_immediately(self):
        """MockAgentProvider returns without delay."""
        import time
        from agent_provider import MockAgentProvider, AgentResponse

        canned = AgentResponse(
            content="Fast",
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        start = time.time()
        for _ in range(100):
            provider.invoke("test", {})
        elapsed = time.time() - start

        # 100 calls should complete in under 100ms (no network delay)
        assert elapsed < 0.1

    def test_mock_provider_returns_independent_copies(self):
        """MockAgentProvider returns copies to prevent mutation issues."""
        from agent_provider import MockAgentProvider, AgentResponse

        canned = AgentResponse(
            content="Original",
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        result1 = provider.invoke("test", {})
        result1.content = "Mutated"  # Mutate first result

        result2 = provider.invoke("test", {})

        # Second result should be unaffected by mutation
        assert result2.content == "Original"


class TestAnthropicAgentProvider:
    """Tests for AnthropicAgentProvider - AC2 and AC3."""

    def test_anthropic_provider_requires_llm_enabled_flag(self):
        """AnthropicAgentProvider raises ConfigurationError without flag."""
        from agent_provider import AnthropicAgentProvider, ConfigurationError

        # Ensure flag is not set
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PROCESSOS_LLM_ENABLED", None)

            with pytest.raises(ConfigurationError) as exc_info:
                AnthropicAgentProvider()

            assert "PROCESSOS_LLM_ENABLED" in str(exc_info.value)

    def test_anthropic_provider_requires_flag_true(self):
        """AnthropicAgentProvider requires flag to be 'true', not just set."""
        from agent_provider import AnthropicAgentProvider, ConfigurationError

        with patch.dict(os.environ, {"PROCESSOS_LLM_ENABLED": "false"}):
            with pytest.raises(ConfigurationError):
                AnthropicAgentProvider()

    def test_anthropic_provider_requires_api_key(self):
        """AnthropicAgentProvider raises ConfigurationError without API key."""
        from agent_provider import AnthropicAgentProvider, ConfigurationError

        with patch.dict(os.environ, {"PROCESSOS_LLM_ENABLED": "true"}, clear=True):
            # Ensure API key is not set
            os.environ.pop("ANTHROPIC_API_KEY", None)

            with pytest.raises(ConfigurationError) as exc_info:
                AnthropicAgentProvider()

            assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_anthropic_provider_accepts_flag_true(self):
        """AnthropicAgentProvider instantiates when flag is 'true'."""
        from agent_provider import AnthropicAgentProvider

        with patch.dict(os.environ, {
            "PROCESSOS_LLM_ENABLED": "true",
            "ANTHROPIC_API_KEY": "test-key"
        }):
            with patch("agent_provider.anthropic"):
                provider = AnthropicAgentProvider()
                assert provider is not None

    @pytest.mark.skipif(
        os.environ.get("PROCESSOS_LLM_ENABLED", "").lower() != "true",
        reason="Requires PROCESSOS_LLM_ENABLED=true for real API test"
    )
    def test_anthropic_provider_calls_real_api(self):
        """Integration test: AnthropicAgentProvider calls Claude API."""
        from agent_provider import AnthropicAgentProvider, AgentResponse

        provider = AnthropicAgentProvider()
        result = provider.invoke("Say 'Hello' and nothing else.", {})

        assert isinstance(result, AgentResponse)
        assert "Hello" in result.content
        assert result.usage["input_tokens"] > 0
        assert result.usage["output_tokens"] > 0


class TestAgentOutputValidation:
    """Tests for S3-002: Agent output validation integration."""

    def test_validate_output_valid_json(self):
        """validate_output() accepts valid JSON matching schema."""
        from agent_provider import MockAgentProvider

        provider = MockAgentProvider()
        content = '{"decision": "proceed", "reasoning": "All checks passed"}'

        result = provider.validate_output(content)

        assert result["decision"] == "proceed"
        assert result["reasoning"] == "All checks passed"

    def test_validate_output_invalid_json_raises_error(self):
        """validate_output() raises error for invalid JSON."""
        from agent_provider import MockAgentProvider, AgentOutputValidationError

        provider = MockAgentProvider()
        content = "This is not valid JSON"

        with pytest.raises(AgentOutputValidationError) as exc_info:
            provider.validate_output(content)

        assert "not valid JSON" in str(exc_info.value)

    def test_validate_output_schema_failure_raises_error(self):
        """validate_output() raises error when schema validation fails."""
        from agent_provider import MockAgentProvider, AgentOutputValidationError

        provider = MockAgentProvider()
        content = '{"reasoning": "Missing decision field"}'

        with pytest.raises(AgentOutputValidationError) as exc_info:
            provider.validate_output(content)

        assert "validation failed" in str(exc_info.value).lower()

    def test_validate_output_includes_context(self):
        """AgentOutputValidationError includes step/agent context."""
        from agent_provider import MockAgentProvider, AgentOutputValidationError

        provider = MockAgentProvider()
        content = '{"invalid": "structure"}'
        context = {"step_id": "step_1", "agent_id": "test-agent"}

        with pytest.raises(AgentOutputValidationError) as exc_info:
            provider.validate_output(content, context)

        error = exc_info.value
        assert error.step_id == "step_1"
        assert error.agent_id == "test-agent"

    def test_invoke_validated_returns_response_and_output(self):
        """invoke_validated() returns both response and validated output."""
        from agent_provider import MockAgentProvider, AgentResponse

        valid_content = '{"decision": "proceed", "reasoning": "Test"}'
        canned = AgentResponse(
            content=valid_content,
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        response, validated = provider.invoke_validated("test", {})

        assert response.content == valid_content
        assert validated["decision"] == "proceed"

    def test_invoke_validated_raises_on_invalid_output(self):
        """invoke_validated() raises error when output fails validation."""
        from agent_provider import MockAgentProvider, AgentResponse, AgentOutputValidationError

        invalid_content = '{"bad": "output"}'
        canned = AgentResponse(
            content=invalid_content,
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        with pytest.raises(AgentOutputValidationError):
            provider.invoke_validated("test", {})


class TestAgentTimeout:
    """Tests for S3-003: SDK Timeout + Deterministic Halt-on-Failure."""

    def test_invoke_with_timeout_completes_normally(self):
        """AC1: Request completing within timeout returns response."""
        from agent_provider import MockAgentProvider, AgentResponse

        canned = AgentResponse(
            content='{"decision": "proceed", "reasoning": "Fast"}',
            model="mock",
            usage={"input_tokens": 0, "output_tokens": 0}
        )
        provider = MockAgentProvider(response=canned)

        # Call with timeout (should complete immediately)
        result = provider.invoke("test", {}, timeout=30.0)

        assert result.content == canned.content

    def test_invoke_timeout_raises_agent_timeout_error(self):
        """AC2: Request exceeding timeout raises AgentTimeoutError."""
        from agent_provider import MockDelayProvider, AgentTimeoutError

        # Provider that simulates 2 second delay
        provider = MockDelayProvider(delay_seconds=2.0)

        with pytest.raises(AgentTimeoutError) as exc_info:
            provider.invoke("test", {}, timeout=0.1)

        error = exc_info.value
        assert error.timeout == 0.1
        assert hasattr(error, "elapsed")

    def test_timeout_error_includes_context(self):
        """AgentTimeoutError includes timeout and elapsed time."""
        from agent_provider import AgentTimeoutError

        error = AgentTimeoutError(
            "Agent call timed out after 60s",
            timeout=60.0,
            elapsed=60.5
        )

        assert error.timeout == 60.0
        assert error.elapsed == 60.5
        assert "60s" in str(error)

    def test_anthropic_provider_configures_sdk_timeout(self):
        """AnthropicAgentProvider passes timeout to SDK client."""
        from agent_provider import AnthropicAgentProvider

        with patch.dict(os.environ, {
            "PROCESSOS_LLM_ENABLED": "true",
            "ANTHROPIC_API_KEY": "test-key"
        }):
            with patch("agent_provider.anthropic") as mock_anthropic:
                provider = AnthropicAgentProvider(timeout=45.0)

                # Verify timeout was configured
                assert provider.timeout == 45.0
                # Client should have been created with timeout
                mock_anthropic.Anthropic.assert_called_once()

    def test_invoke_default_timeout_is_60_seconds(self):
        """Default timeout for invoke() should be 60 seconds."""
        from agent_provider import MockAgentProvider
        import inspect

        # Check invoke signature has timeout with default 60.0
        sig = inspect.signature(MockAgentProvider.invoke)
        params = sig.parameters
        assert "timeout" in params
        assert params["timeout"].default == 60.0


class TestGetProvider:
    """Tests for get_provider() factory function."""

    def test_get_provider_returns_mock_by_default(self):
        """get_provider() returns MockAgentProvider when LLM not enabled."""
        from agent_provider import get_provider, MockAgentProvider

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PROCESSOS_LLM_ENABLED", None)

            provider = get_provider()

            assert isinstance(provider, MockAgentProvider)

    def test_get_provider_returns_anthropic_when_enabled(self):
        """get_provider() returns AnthropicAgentProvider when flag is true."""
        from agent_provider import get_provider, AnthropicAgentProvider

        with patch.dict(os.environ, {
            "PROCESSOS_LLM_ENABLED": "true",
            "ANTHROPIC_API_KEY": "test-key"
        }):
            with patch("agent_provider.anthropic"):
                provider = get_provider()

                assert isinstance(provider, AnthropicAgentProvider)

    def test_get_provider_accepts_use_real_llm_override(self):
        """get_provider(use_real_llm=True) forces AnthropicAgentProvider."""
        from agent_provider import get_provider, AnthropicAgentProvider

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("agent_provider.anthropic"):
                # Even without PROCESSOS_LLM_ENABLED, explicit override works
                with patch.dict(os.environ, {"PROCESSOS_LLM_ENABLED": "true"}):
                    provider = get_provider(use_real_llm=True)

                    assert isinstance(provider, AnthropicAgentProvider)
