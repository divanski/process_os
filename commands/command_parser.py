"""
ProcessOS Command Parser

Parses natural language commands into structured TaskRequests.
Deterministic: same command text = same TaskRequest.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from .task_request import TaskContext, TaskParameters, TaskRequest, TaskTarget


class CommandParser:
    """
    Parses user commands into TaskRequest objects.

    Determinism guarantees:
    - Same command text = same command_id
    - Same command text = same parsed structure
    - Timestamps only in context (not in core ID/structure)
    """

    # Intent patterns: ordered list for priority matching
    INTENT_PATTERNS: List[Tuple[str, List[str]]] = [
        ("integrate", [
            r"\b(?:integrate|add|connect|link)\b.*\b(?:courier|carrier|shipping)\b",
            r"\b(?:courier|carrier)\b.*\b(?:integration|setup)\b",
        ]),
        ("map_api", [
            r"\b(?:map|create|generate)\b.*\b(?:api|API)\b",
            r"\b(?:api|API)\b.*\b(?:mapping|map)\b",
        ]),
        ("detect", [
            r"\b(?:detect|find|discover|identify)\b",
            r"\b(?:detection|discovery)\b",
        ]),
        ("analyze", [
            r"\b(?:analyze|analyse|review|examine|inspect)\b",
            r"\b(?:analysis|review)\b",
        ]),
        ("generate", [
            r"\b(?:generate|create|build|make)\b.*\b(?:code|module|component)\b",
        ]),
        ("validate", [
            r"\b(?:validate|verify|check|test)\b",
            r"\b(?:validation|verification)\b",
        ]),
    ]

    # Target type patterns
    TARGET_TYPE_PATTERNS: Dict[str, List[str]] = {
        "courier": [r"\b(?:courier|carrier|shipping|logistics)\b"],
        "api": [r"\b(?:api|API|endpoint|rest|graphql)\b"],
        "service": [r"\b(?:service|microservice|backend)\b"],
        "component": [r"\b(?:component|widget|ui|frontend)\b"],
        "module": [r"\b(?:module|library|package)\b"],
    }

    # Priority keywords
    PRIORITY_KEYWORDS = {
        "critical": ["urgent", "critical", "asap", "immediately", "emergency"],
        "high": ["important", "high", "priority", "soon"],
        "low": ["low", "whenever", "eventually", "backlog", "nice to have"],
    }

    # Capability keywords (domain-specific)
    CAPABILITY_KEYWORDS = {
        "shipment_tracking": ["tracking", "track", "trace"],
        "label_generation": ["label", "labels", "printing"],
        "rate_calculation": ["rate", "rates", "pricing", "quote"],
        "pickup_scheduling": ["pickup", "collection", "schedule"],
        "return_handling": ["return", "returns", "rma"],
        "international_shipping": ["international", "cross-border", "global"],
        "notifications": ["notify", "notification", "alerts", "sms", "email"],
        "webhooks": ["webhook", "callback", "event"],
    }

    def __init__(self, schema_path: Optional[Path] = None):
        """
        Initialize parser with schema for validation.

        Args:
            schema_path: Path to task-request.schema.json
        """
        if schema_path is None:
            schema_path = (
                Path(__file__).parent.parent / "schemas" / "task-request.schema.json"
            )

        self.schema_path = schema_path
        self._schema: Optional[Dict[str, Any]] = None

    @property
    def schema(self) -> Dict[str, Any]:
        """Lazy-load schema."""
        if self._schema is None:
            with open(self.schema_path) as f:
                self._schema = json.load(f)
        return self._schema

    def _generate_command_id(self, command: str) -> str:
        """
        Generate deterministic command ID from text.

        Same command text always produces same ID.
        """
        canonical = command.strip().lower()
        hash_hex = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        return f"cmd-{hash_hex}"

    def _to_identifier(self, name: str) -> str:
        """Convert name to kebab-case identifier."""
        # Remove special characters except alphanumeric and spaces
        clean = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
        # Replace spaces with hyphens
        kebab = re.sub(r"\s+", "-", clean.strip().lower())
        # Ensure starts with letter
        if kebab and not kebab[0].isalpha():
            kebab = "x-" + kebab
        # Truncate to 50 chars
        return kebab[:50] if kebab else "unnamed"

    def _detect_intent(self, command: str) -> str:
        """Detect command intent from text."""
        command_lower = command.lower()

        for intent, patterns in self.INTENT_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return intent

        return "custom"

    def _detect_target_type(self, command: str) -> str:
        """Detect target type from command text."""
        command_lower = command.lower()

        for target_type, patterns in self.TARGET_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return target_type

        return "custom"

    def _extract_target_name(self, command: str) -> str:
        """
        Extract target name from command.

        Looks for:
        1. Quoted strings
        2. Capitalized words after keywords
        3. Named entities
        """
        # Try quoted strings first
        quoted = re.search(r'["\']([^"\']+)["\']', command)
        if quoted:
            return quoted.group(1).strip()

        # Try "for X" or "with X" patterns
        for_pattern = re.search(
            r"\b(?:for|with|to|into)\s+([A-Z][A-Za-z0-9_\-\s]{1,30})",
            command,
        )
        if for_pattern:
            return for_pattern.group(1).strip()

        # Try capitalized words (likely proper nouns)
        caps = re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\b", command)
        if caps:
            # Filter out common verbs/nouns
            common = {"Create", "Add", "Map", "Generate", "Build", "The", "For"}
            caps = [c for c in caps if c not in common]
            if caps:
                return caps[0]

        # Last resort: use first noun-like word after verb
        words = command.split()
        for i, word in enumerate(words):
            if word.lower() in ["integrate", "add", "map", "create", "detect"]:
                if i + 1 < len(words):
                    return words[i + 1].strip(".,;:!?")

        return "unnamed-target"

    def _detect_priority(self, command: str) -> str:
        """Detect priority from command text."""
        command_lower = command.lower()

        for priority, keywords in self.PRIORITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in command_lower:
                    return priority

        return "medium"

    def _extract_capabilities(self, command: str, target_type: str) -> List[str]:
        """Extract required capabilities from command."""
        command_lower = command.lower()
        capabilities = []

        for capability, keywords in self.CAPABILITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in command_lower:
                    capabilities.append(capability)
                    break

        # Add default capabilities based on target type
        if not capabilities:
            if target_type == "courier":
                capabilities = ["shipment_tracking", "label_generation"]
            elif target_type == "api":
                capabilities = ["api_mapping"]

        return sorted(set(capabilities))

    def _extract_constraints(self, command: str) -> List[str]:
        """Extract constraints from command."""
        constraints = []

        # Pattern-based constraint extraction
        constraint_patterns = [
            (r"\bno\s+(\w+)", lambda m: f"no_{m.group(1).lower()}"),
            (r"\bmust\s+(?:be\s+)?(\w+)", lambda m: f"must_{m.group(1).lower()}"),
            (r"\bread[- ]?only\b", lambda m: "read_only"),
            (r"\bno[- ]?write\b", lambda m: "no_write"),
            (r"\btest[- ]?only\b", lambda m: "test_only"),
        ]

        for pattern, extractor in constraint_patterns:
            for match in re.finditer(pattern, command, re.IGNORECASE):
                constraints.append(extractor(match))

        return sorted(set(constraints))

    def parse(
        self,
        command: str,
        host_root: Optional[str] = None,
        include_timestamp: bool = True,
    ) -> TaskRequest:
        """
        Parse user command into TaskRequest.

        Args:
            command: Natural language command text
            host_root: Root path of host project (optional)
            include_timestamp: Whether to include parsed_at in context

        Returns:
            TaskRequest object

        Raises:
            ValueError: If command is empty or invalid
            jsonschema.ValidationError: If result doesn't match schema
        """
        if not command or not command.strip():
            raise ValueError("Command cannot be empty")

        command = command.strip()

        # Generate deterministic ID
        command_id = self._generate_command_id(command)

        # Detect intent
        intent = self._detect_intent(command)

        # Extract target
        target_type = self._detect_target_type(command)
        target_name = self._extract_target_name(command)
        target = TaskTarget(
            name=target_name,
            identifier=self._to_identifier(target_name),
            type=target_type,
        )

        # Extract parameters
        parameters = TaskParameters(
            priority=self._detect_priority(command),
            capabilities=self._extract_capabilities(command, target_type),
            constraints=self._extract_constraints(command),
            options={},
        )

        # Build context
        context = TaskContext(
            original_command=command,
            parsed_at=(
                datetime.now(timezone.utc).isoformat()
                if include_timestamp
                else ""
            ),
            host_root=host_root or "",
        )

        # Create request
        request = TaskRequest(
            command_id=command_id,
            intent=intent,
            target=target,
            parameters=parameters,
            context=context,
        )

        # Validate against schema
        self.validate(request)

        return request

    def validate(self, request: TaskRequest) -> None:
        """
        Validate TaskRequest against schema.

        Raises:
            jsonschema.ValidationError: If validation fails
        """
        jsonschema.validate(request.to_dict(), self.schema)

    def parse_json(self, json_str: str) -> TaskRequest:
        """
        Parse JSON string into TaskRequest.

        Args:
            json_str: JSON string representation

        Returns:
            TaskRequest object
        """
        request = TaskRequest.from_json(json_str)
        self.validate(request)
        return request
