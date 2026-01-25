"""
ProcessOS Command Parser

Parses human commands into structured SquadRequest objects.
Deterministic: same command = same SquadRequest.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

import jsonschema


@dataclass
class SquadRequest:
    """Structured representation of a human command."""
    request_id: str
    command_type: str
    target: Dict[str, str]
    parameters: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with sorted keys for determinism."""
        return json.loads(json.dumps(asdict(self), sort_keys=True))

    def to_json(self) -> str:
        """Serialize to deterministic JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


class CommandParser:
    """
    Parses human commands into SquadRequest objects.

    Determinism guarantees:
    - Same command text = same request_id
    - Same command text = same parsed structure
    - No timestamps in output (only in telemetry)
    """

    # Command patterns for different types
    # Order matters: more specific patterns first, then generic
    PATTERNS = [
        # Courier integration patterns - order matters (more specific first)
        ("courier_integration", [
            r"(?:integrate|add|connect|link)\s+(?:courier|carrier|shipping|logistics)\s+([A-Za-z0-9_\- ]+)",
            r"(?:courier|carrier|shipping|logistics)\s+([A-Za-z0-9_\- ]+)\s+(?:integration|setup|connect)",
        ]),
        # API mapping patterns
        ("api_mapping", [
            r"(?:map|create|generate)\s+(?:api|API)(?:\s+(?:for|mapping))?\s+(?:for\s+)?(?:to\s+)?([A-Za-z0-9_\- ]+)",
            r"(?:api|API)\s+(?:mapping|map)(?:\s+for)?\s+([A-Za-z0-9_\- ]+)",
        ]),
        # Detection/discovery patterns
        ("detection_rules", [
            r"(?:detect|find|discover|identify|create\s+detection)\s+(?:for\s+)?(?:rules?\s+for\s+)?([A-Za-z0-9_\- ]+)",
            r"(?:detection|discovery)(?:\s+(?:rules?|patterns?))?\s+(?:for\s+)?([A-Za-z0-9_\- ]+)",
        ]),
        # Generic integration patterns (fallback)
        ("integration", [
            r"(?:integrate|add|connect)\s+(?:integration\s+)?(?:for\s+)?(?:with\s+)?['\"]?([A-Za-z0-9_\- ]+)['\"]?(?:\s+api|\s+service)?",
            r"(?:create|setup)\s+(?:integration\s+)?(?:for\s+)?(?:with\s+)?['\"]?([A-Za-z0-9_\- ]+)['\"]?(?:\s+api|\s+service)?",
        ]),
    ]

    # Capability keywords for domain-specific feature extraction
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
            schema_path: Path to squad-request.schema.json
        """
        if schema_path is None:
            schema_path = Path(__file__).parent.parent / "schemas" / "squad-request.schema.json"

        self.schema_path = schema_path
        self._schema = None

    @property
    def schema(self) -> Dict[str, Any]:
        """Lazy-load schema."""
        if self._schema is None:
            with open(self.schema_path) as f:
                self._schema = json.load(f)
        return self._schema

    def _generate_request_id(self, command: str) -> str:
        """Generate deterministic request ID from command."""
        canonical = command.strip().lower()
        hash_hex = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        return f"req-{hash_hex}"

    def _to_identifier(self, name: str) -> str:
        """Convert name to kebab-case identifier."""
        # Remove special characters, convert to lowercase
        clean = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
        # Replace spaces with hyphens
        kebab = re.sub(r'\s+', '-', clean.strip().lower())
        # Ensure starts with letter
        if kebab and not kebab[0].isalpha():
            kebab = 'x-' + kebab
        return kebab[:50]  # Max 50 chars

    def _detect_command_type(self, command: str) -> tuple[str, str]:
        """
        Detect command type and extract target name.

        Returns:
            Tuple of (command_type, target_name)
        """
        command_lower = command.lower()

        # PATTERNS is a list of (type, patterns) for ordered matching
        for cmd_type, patterns in self.PATTERNS:
            for pattern in patterns:
                match = re.search(pattern, command, re.IGNORECASE)
                if match:
                    return cmd_type, match.group(1).strip()

        # Default: treat whole command as custom with extracted name
        # Try to extract any quoted string as target
        quoted = re.search(r'["\']([^"\']+)["\']', command)
        if quoted:
            return "custom", quoted.group(1).strip()

        # Last resort: use first capitalized word
        words = command.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                return "custom", word

        return "custom", "unnamed-target"

    def _extract_parameters(self, command: str, command_type: str) -> Dict[str, Any]:
        """Extract parameters from command text."""
        params: Dict[str, Any] = {
            "priority": "medium",
            "capabilities": [],
            "constraints": [],
        }

        # Detect capabilities from keywords
        command_lower = command.lower()
        for capability, keywords in self.CAPABILITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in command_lower:
                    if capability not in params["capabilities"]:
                        params["capabilities"].append(capability)

        # Detect priority
        if any(word in command_lower for word in ["urgent", "critical", "asap"]):
            params["priority"] = "critical"
        elif any(word in command_lower for word in ["important", "high"]):
            params["priority"] = "high"
        elif any(word in command_lower for word in ["low", "whenever", "eventually"]):
            params["priority"] = "low"

        # Detect constraints (generic)
        constraint_patterns = [
            (r"no\s+(\w+)", lambda m: f"no_{m.group(1).lower()}"),
            (r"must\s+(?:be\s+)?(\w+)", lambda m: f"must_{m.group(1).lower()}"),
            (r"read[- ]?only", lambda m: "read_only"),
        ]
        for pattern, extractor in constraint_patterns:
            for match in re.finditer(pattern, command, re.IGNORECASE):
                params["constraints"].append(extractor(match))

        return params

    def parse(self, command: str) -> SquadRequest:
        """
        Parse human command into SquadRequest.

        Args:
            command: Human command text

        Returns:
            SquadRequest object

        Raises:
            ValueError: If command is empty or invalid
            jsonschema.ValidationError: If result doesn't match schema
        """
        if not command or not command.strip():
            raise ValueError("Command cannot be empty")

        command = command.strip()

        # Generate deterministic ID
        request_id = self._generate_request_id(command)

        # Detect type and target
        command_type, target_name = self._detect_command_type(command)

        # Build target
        target = {
            "name": target_name,
            "identifier": self._to_identifier(target_name),
        }

        # Extract parameters
        parameters = self._extract_parameters(command, command_type)

        # Build request
        request = SquadRequest(
            request_id=request_id,
            command_type=command_type,
            target=target,
            parameters=parameters,
            context={"original_command": command},
        )

        # Validate against schema
        self.validate(request)

        return request

    def validate(self, request: SquadRequest) -> None:
        """
        Validate SquadRequest against schema.

        Raises:
            jsonschema.ValidationError: If validation fails
        """
        jsonschema.validate(request.to_dict(), self.schema)

    def parse_json(self, json_str: str) -> SquadRequest:
        """
        Parse JSON string into SquadRequest.

        Args:
            json_str: JSON string representation

        Returns:
            SquadRequest object
        """
        data = json.loads(json_str)
        request = SquadRequest(**data)
        self.validate(request)
        return request
