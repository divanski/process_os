"""
ProcessOS Intent Parser Module

Parses natural language integration requests using LLM analysis.
Handles clarification workflows for ambiguous requests.
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .types import (
    Clarification,
    ClarificationOption,
    Intent,
    IntegrationScope,
)

if TYPE_CHECKING:
    from ..discovery import ProjectContext


# JSON schema for LLM response validation
INTENT_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["integration_type", "scope", "confidence"],
    "properties": {
        "integration_type": {"type": "string"},
        "target_service": {"type": ["string", "null"]},
        "scope": {"type": "string", "enum": ["full_crud", "read_only", "write_only", "specific_operations"]},
        "operations": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "clarifications": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "question", "options"],
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array"},
                    "default": {"type": ["string", "null"]},
                    "priority": {"type": "integer"},
                },
            },
        },
    },
}

# System prompt for intent analysis
INTENT_ANALYSIS_PROMPT = """You are an intent analyzer for the ProcessOS integration system.

Analyze the user's integration request and extract:
1. integration_type: The category of integration (supplier_api, payment, notification, storage, analytics, authentication, custom)
2. target_service: The specific service name if mentioned (e.g., DHL, Stripe, SendGrid)
3. scope: The scope of operations needed (full_crud, read_only, write_only, specific_operations)
4. operations: List of specific operations mentioned or implied
5. confidence: How confident you are in the classification (0.0-1.0)
6. clarifications: List of questions if the request is ambiguous

If the project context is provided, use it to:
- Suggest which existing models might be relevant
- Understand the project's technology stack
- Infer common patterns for that framework

Respond with valid JSON only. No markdown, no explanation."""

COMPOUND_DETECTION_PROMPT = """Analyze if this request contains multiple distinct integration requests.

If compound (multiple integrations):
- Set is_compound: true
- Return array of intents

If simple (single integration):
- Set is_compound: false
- Return single intent

Respond with valid JSON only."""


class IntentParser:
    """
    Parses natural language integration requests using LLM analysis.

    Handles:
    - Intent classification (type, scope, operations)
    - Clarification workflow for ambiguous requests
    - Multi-intent detection for compound requests
    - Retry logic for LLM failures
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(
        self,
        project_context: Optional["ProjectContext"] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize the IntentParser.

        Args:
            project_context: Optional project context for better analysis
            llm_client: Optional custom LLM client (for testing)
        """
        self.project_context = project_context
        self._llm_client = llm_client
        self._on_clarification: Optional[Callable[[Clarification], str]] = None

    def parse(self, request: str) -> Intent:
        """
        Parse a natural language integration request.

        Args:
            request: Natural language integration request

        Returns:
            Intent object with parsed details

        Raises:
            IntentParseError: If intent cannot be determined
            LLMUnavailableError: If LLM API is unavailable after retries
        """
        from . import IntentParseError

        if not request or not request.strip():
            raise IntentParseError("Empty request", raw_request=request)

        # Call LLM with retry logic
        response = self._call_llm(request)

        # Validate response
        self._validate_response(response)

        # Build Intent from response
        return self._build_intent(request, response)

    def parse_compound(self, request: str) -> List[Intent]:
        """
        Parse a potentially compound integration request.

        Detects if the request contains multiple distinct integrations
        and returns a list of Intent objects.

        Args:
            request: Natural language integration request

        Returns:
            List of Intent objects (1 for simple, multiple for compound)
        """
        # Check for compound request indicators
        self._build_compound_prompt(request)
        response = self._call_llm(request, compound_check=True)

        if response.get("is_compound") and "intents" in response:
            # Multiple intents detected
            intents = []
            for intent_data in response["intents"]:
                intent = self._build_intent(request, intent_data)
                intents.append(intent)
            return intents
        else:
            # Single intent
            return [self._build_intent(request, response)]

    def apply_clarification(
        self,
        intent: Intent,
        clarification_id: str,
        option_id: str,
        custom_value: Optional[str] = None,
    ) -> Intent:
        """
        Apply a clarification answer and re-analyze the intent.

        Args:
            intent: The intent needing clarification
            clarification_id: ID of the clarification being resolved
            option_id: Selected option ID or 'custom'
            custom_value: Custom value if option_id is 'custom'

        Returns:
            Updated Intent with clarification applied
        """
        # Record the resolution
        intent.resolve_clarification(clarification_id, option_id, custom_value)

        # Build context with resolved clarifications
        context = self._build_clarification_context(intent)

        # Re-analyze with clarification context
        response = self._call_llm(intent.raw_request, clarification_context=context)

        # Build updated intent preserving resolved clarifications
        updated_intent = self._build_intent(intent.raw_request, response)
        updated_intent.clarifications_resolved = intent.clarifications_resolved.copy()

        return updated_intent

    def needs_clarification(self, intent: Intent) -> bool:
        """
        Check if intent needs user clarification.

        Args:
            intent: Intent to check

        Returns:
            True if clarification needed
        """
        return intent.needs_clarification

    def _call_llm(
        self,
        request: str,
        clarification_context: Optional[Dict[str, Any]] = None,
        compound_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Call LLM with retry logic.

        Args:
            request: User request
            clarification_context: Optional context from clarifications
            compound_check: Whether this is a compound check

        Returns:
            Parsed JSON response

        Raises:
            LLMUnavailableError: If all retries fail
        """
        from . import LLMUnavailableError, IntentParseError

        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._call_llm_raw(request, clarification_context, compound_check)

                # Validate basic structure
                if not isinstance(response, dict):
                    raise IntentParseError("Invalid response format from LLM")

                return response

            except IntentParseError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                continue

        raise LLMUnavailableError(
            f"LLM API unavailable after {self.MAX_RETRIES} attempts: {last_error}"
        )

    def _call_llm_raw(
        self,
        request: str,
        clarification_context: Optional[Dict[str, Any]] = None,
        compound_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Make raw LLM API call.

        This method is separated to allow easy mocking in tests.

        Args:
            request: User request
            clarification_context: Optional context from clarifications
            compound_check: Whether this is a compound check

        Returns:
            Parsed JSON response
        """
        from . import IntentParseError

        # Build the prompt
        if compound_check:
            system_prompt = COMPOUND_DETECTION_PROMPT
        else:
            system_prompt = INTENT_ANALYSIS_PROMPT

        user_prompt = self._build_user_prompt(request, clarification_context)

        # Use provided client or default
        if self._llm_client:
            response_text = self._llm_client.complete(system_prompt, user_prompt)
        else:
            # Default: use Claude API through ProcessOS
            response_text = self._default_llm_call(system_prompt, user_prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            response = self._extract_json(response_text)
            return response
        except json.JSONDecodeError as e:
            raise IntentParseError(f"Invalid JSON response from LLM: {e}")

    def _default_llm_call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Make LLM call using default ProcessOS configuration.

        Uses the AnthropicClient from process_os.llm module.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt

        Returns:
            LLM response text

        Raises:
            LLMUnavailableError: If LLM API is unavailable or authentication fails
        """
        from . import LLMUnavailableError

        try:
            from ..llm import get_llm_client, LLMError, AuthenticationError, RateLimitError

            client = get_llm_client()
            response = client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return response.content

        except AuthenticationError as e:
            raise LLMUnavailableError(
                f"LLM authentication failed. Check your ANTHROPIC_API_KEY: {e}"
            )
        except RateLimitError as e:
            raise LLMUnavailableError(
                f"LLM rate limited. Please try again later: {e}"
            )
        except LLMError as e:
            raise LLMUnavailableError(f"LLM request failed: {e}")
        except ImportError as e:
            raise LLMUnavailableError(
                f"LLM module not available. Install anthropic package: {e}"
            )

    def _build_user_prompt(
        self,
        request: str,
        clarification_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the user prompt for LLM analysis."""
        parts = [f"Integration Request: {request}"]

        # Add project context if available
        if self.project_context:
            context_info = {
                "language": self.project_context.language,
                "framework": self.project_context.framework,
                "models": [m.name for m in self.project_context.models[:10]],
                "routes_count": len(self.project_context.routes),
                "services": [s.name for s in self.project_context.services[:10]],
            }
            parts.append(f"\nProject Context:\n{json.dumps(context_info, indent=2)}")

        # Add clarification context if provided
        if clarification_context:
            parts.append(f"\nPrevious Clarifications:\n{json.dumps(clarification_context, indent=2)}")

        return "\n".join(parts)

    def _build_compound_prompt(self, request: str) -> str:
        """Build prompt for compound request detection."""
        return f"""Analyze if this contains multiple distinct integrations:

Request: {request}

Indicators of compound request:
- "and" connecting different services
- Multiple service names
- Different integration types mentioned

Respond with JSON containing is_compound (boolean) and either single intent or array of intents."""

    def _build_clarification_context(self, intent: Intent) -> Dict[str, Any]:
        """Build context dict from resolved clarifications."""
        return {
            "resolved": [
                {
                    "id": r.clarification_id,
                    "answer": r.selected_option,
                    "custom_value": r.custom_value,
                }
                for r in intent.clarifications_resolved
            ],
            "original_request": intent.raw_request,
            "current_type": intent.integration_type,
        }

    def _validate_response(self, response: Dict[str, Any]) -> None:
        """
        Validate LLM response against schema.

        Args:
            response: LLM response dict

        Raises:
            IntentParseError: If validation fails
        """
        from . import IntentParseError

        # Check required fields
        required = ["integration_type", "confidence"]
        for field in required:
            if field not in response:
                raise IntentParseError(f"Missing required field: {field}")

        # Validate confidence range
        confidence = response.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            raise IntentParseError(f"Invalid confidence value: {confidence}")

        # Validate scope if present
        valid_scopes = ["full_crud", "read_only", "write_only", "specific_operations"]
        scope = response.get("scope", "full_crud")
        if scope not in valid_scopes:
            raise IntentParseError(f"Invalid scope: {scope}")

    def _build_intent(self, raw_request: str, response: Dict[str, Any]) -> Intent:
        """
        Build Intent object from LLM response.

        Args:
            raw_request: Original user request
            response: Parsed LLM response

        Returns:
            Intent object
        """
        # Parse clarifications if present
        clarifications = []
        for c in response.get("clarifications", []):
            # Skip non-dict clarifications (LLM may return strings)
            if not isinstance(c, dict):
                continue

            # Parse options, handling both dict and string formats
            raw_options = c.get("options", [])
            options = []
            for i, o in enumerate(raw_options):
                if isinstance(o, dict):
                    options.append(ClarificationOption(
                        id=o.get("id", f"opt_{i}"),
                        label=o.get("label", str(o)),
                        description=o.get("description", ""),
                        implications=o.get("implications", ""),
                    ))
                elif isinstance(o, str):
                    # Handle string options
                    options.append(ClarificationOption(
                        id=f"opt_{i}",
                        label=o,
                        description="",
                        implications="",
                    ))

            clarifications.append(
                Clarification(
                    id=c.get("id", f"clarify_{len(clarifications)}"),
                    question=c.get("question", ""),
                    options=options,
                    default=c.get("default"),
                    priority=c.get("priority", 2),
                )
            )

        # Map scope string to enum
        scope_str = response.get("scope", "full_crud")
        scope = IntegrationScope(scope_str)

        return Intent(
            raw_request=raw_request,
            integration_type=response.get("integration_type", ""),
            target_service=response.get("target_service"),
            scope=scope,
            operations=response.get("operations", []),
            analyzed_at=datetime.now(),
            confidence=response.get("confidence", 0.0),
            clarifications_needed=clarifications,
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM response text.

        Handles responses that may contain markdown code blocks.

        Args:
            text: Raw LLM response

        Returns:
            Parsed JSON dict
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find JSON object in text
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            return json.loads(brace_match.group(0))

        raise json.JSONDecodeError("No valid JSON found", text, 0)
