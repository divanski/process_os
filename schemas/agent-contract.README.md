# Agent Contract Schema Reference

## Overview

All ProcessOS agent outputs must conform to the `agent-output.schema.json` schema. This ensures consistent, parseable responses that the engine can process reliably.

**Key Principle:** Strict validation with `additionalProperties: false`. Invalid output fails immediately with a clear error message.

---

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["decision", "reasoning"],
  "additionalProperties": false,
  "properties": {
    "decision": {
      "type": "string",
      "enum": ["proceed", "halt", "escalate"]
    },
    "reasoning": {
      "type": "string",
      "minLength": 1
    },
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["kind", "content"],
        "additionalProperties": false,
        "properties": {
          "kind": { "type": "string" },
          "content": { "type": "string" }
        }
      }
    }
  }
}
```

---

## Required Fields

### `decision` (required)

The agent's decision about how the workflow should proceed.

| Value | Meaning |
|-------|---------|
| `"proceed"` | Continue to the next step |
| `"halt"` | Stop workflow execution immediately |
| `"escalate"` | Pause for human review before continuing |

**Example:**
```json
"decision": "proceed"
```

### `reasoning` (required)

A non-empty string explaining why the agent made this decision. Used for audit trails and debugging.

**Constraints:**
- Must be a string
- Cannot be empty (`minLength: 1`)

**Example:**
```json
"reasoning": "All validation checks passed. Input data meets requirements."
```

---

## Optional Fields

### `artifacts` (optional)

An array of generated content items. Use for reports, analysis results, recommendations, etc.

**Each artifact requires:**
- `kind`: Type identifier (e.g., `"report"`, `"analysis"`, `"recommendation"`)
- `content`: The actual content string

**Constraints:**
- `additionalProperties: false` on each artifact object

**Example:**
```json
"artifacts": [
  {
    "kind": "analysis",
    "content": "## Analysis Results\n\n- Finding 1: ...\n- Finding 2: ..."
  },
  {
    "kind": "recommendation",
    "content": "Based on analysis, recommend proceeding with Option A."
  }
]
```

---

## Examples

### Valid Output: Minimal

```json
{
  "decision": "proceed",
  "reasoning": "All checks passed."
}
```

### Valid Output: With Artifacts

```json
{
  "decision": "proceed",
  "reasoning": "Analysis complete. Generated summary report.",
  "artifacts": [
    {
      "kind": "report",
      "content": "# Summary Report\n\nKey findings:\n- Item 1\n- Item 2"
    }
  ]
}
```

### Valid Output: Halt Decision

```json
{
  "decision": "halt",
  "reasoning": "Critical validation error: required field 'user_id' is missing from input data."
}
```

### Valid Output: Escalate Decision

```json
{
  "decision": "escalate",
  "reasoning": "Detected potential compliance issue requiring human review before proceeding."
}
```

---

## Invalid Output Examples

### Missing Required Field: `decision`

```json
{
  "reasoning": "Some reasoning here"
}
```

**Error:**
```
ValidationError: Missing required field: 'decision'
```

### Missing Required Field: `reasoning`

```json
{
  "decision": "proceed"
}
```

**Error:**
```
ValidationError: Missing required field: 'reasoning'
```

### Empty Reasoning

```json
{
  "decision": "proceed",
  "reasoning": ""
}
```

**Error:**
```
ValidationError: Field 'reasoning' cannot be empty (minLength: 1)
```

### Invalid Decision Value

```json
{
  "decision": "maybe",
  "reasoning": "Uncertain about next steps"
}
```

**Error:**
```
ValidationError: Invalid value for 'decision': must be one of ['proceed', 'halt', 'escalate']
```

### Extra Field (Strict Mode)

```json
{
  "decision": "proceed",
  "reasoning": "Valid reasoning",
  "confidence": 0.95
}
```

**Error:**
```
ValidationError: Extra field not allowed: 'confidence' (strict mode rejects additional properties)
```

### Typo in Field Name

```json
{
  "desicion": "proceed",
  "reasoning": "Typo in decision"
}
```

**Error:**
```
ValidationError: Missing required field: 'decision'
ValidationError: Extra field not allowed: 'desicion'
```

### Invalid Artifact Structure

```json
{
  "decision": "proceed",
  "reasoning": "Valid",
  "artifacts": [
    {
      "kind": "report"
    }
  ]
}
```

**Error:**
```
ValidationError: Missing required field in artifact: 'content'
```

### Extra Field in Artifact

```json
{
  "decision": "proceed",
  "reasoning": "Valid",
  "artifacts": [
    {
      "kind": "report",
      "content": "Report text",
      "metadata": {"author": "agent"}
    }
  ]
}
```

**Error:**
```
ValidationError: Extra field not allowed in artifact: 'metadata'
```

---

## Validation in Code

### Using ContractValidator

```python
from process_os.runtime.contract_validator import ContractValidator, ValidationError

validator = ContractValidator()

# Valid output
output = {
    "decision": "proceed",
    "reasoning": "All checks passed"
}
validated = validator.validate(output)  # Returns output unchanged

# Invalid output
try:
    validator.validate({"reasoning": "Missing decision"})
except ValidationError as e:
    print(f"Validation failed: {e}")
    print(f"Field: {e.field}")
    print(f"Schema path: {e.schema_path}")
```

### Using AgentProvider.validate_output()

```python
from process_os.runtime.agent_provider import MockAgentProvider, AgentOutputValidationError

provider = MockAgentProvider()

# Validate raw JSON string
try:
    output = provider.validate_output(
        '{"decision": "proceed", "reasoning": "Valid"}',
        context={"step_id": "step_1", "agent_id": "analyst"}
    )
except AgentOutputValidationError as e:
    print(f"Agent output invalid: {e}")
    print(f"Step: {e.step_id}, Agent: {e.agent_id}")
```

---

## Error Handling Best Practices

1. **Catch ValidationError specifically:** Don't catch generic Exception
2. **Log the field name:** Use `error.field` for debugging
3. **Include context:** Wrap in AgentOutputValidationError with step/agent IDs
4. **Fail fast:** Don't attempt to "fix" invalid output

---

## Schema File Location

- Schema: `process_os/schemas/agent-output.schema.json`
- Validator: `process_os/runtime/contract_validator.py`
- Tests: `process_os/runtime/tests/test_contract_validator.py`

---

## References

- [ADR-004: Agent Provider Architecture](../docs/adr/ADR-004-agent-provider-architecture.md)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/schema)
