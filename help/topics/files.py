"""
ProcessOS File Help Topics (T047)

Explains the purpose of each file created by ProcessOS.
"""

from ..explainer import HelpExplainer, HelpTopic


def register_file_topics(explainer: HelpExplainer) -> None:
    """Register file explanation topics."""

    # Main directory structure
    explainer.register_topic(HelpTopic(
        topic_id="files",
        title="ProcessOS File Structure",
        category="Structure",
        content="""
ProcessOS creates a minimal file structure in your project:

## Root Directory

```
.processos/           # All ProcessOS files (single root item)
├── config.yaml       # Unified project configuration
├── claude/           # Claude AI instructions
│   ├── INSTRUCTIONS.md
│   ├── CONTRACTS.md
│   ├── ENTRYPOINT_PROMPT.txt
│   └── PROJECT_CONTEXT.json
└── workspaces/       # Created on-demand for task execution
```

## Design Principles

1. **Single Root Item**: Only `.processos/` is added to your project root
2. **Lazy Creation**: Directories are created only when needed
3. **Unified Config**: Single `config.yaml` instead of multiple files
4. **Self-Contained**: All ProcessOS data stays in `.processos/`

## What Gets Created When

- **processos init**: Creates `.processos/config.yaml` and `.processos/claude/`
- **processos cmd**: Creates `.processos/workspaces/<id>/` for each task
- **processos interactive**: No new files (uses existing config)

## Cleanup

To remove ProcessOS from a project:
```bash
rm -rf .processos/
```

This completely removes ProcessOS without affecting your code.
""",
        related_topics=["config", "workspace"],
        see_also=["processos help config", "processos help workspace"],
    ))

    # config.yaml explanation
    explainer.register_topic(HelpTopic(
        topic_id="file-config",
        title="config.yaml File",
        category="Structure",
        content="""
The `config.yaml` file is the unified configuration for your ProcessOS project.

## Location

```
.processos/config.yaml
```

## Structure

```yaml
version: "1.0.0"
created_at: "2024-01-15T10:30:00Z"
updated_at: "2024-01-15T10:30:00Z"

project:
  name: "my-project"
  root: "."

binding:
  binding_id: "bind-abc123"
  processos_version: "0.8.0"

fingerprint:
  fingerprint_id: "fp-xyz789"
  stacks:
    - stack_id: "python"
      confidence: "high"
      version_hint: "3.11"
  frameworks:
    - framework_id: "fastapi"
      stack: "python"
      confidence: "high"

settings:
  observability:
    mode: "minimal"
  credentials:
    sources: ["env", "keychain", "file"]
  pillars: []
```

## Key Sections

- **project**: Basic project information
- **binding**: ProcessOS instance binding (links project to ProcessOS)
- **fingerprint**: Detected technology stack
- **settings**: Customizable settings

## Modifying

Use the CLI to safely modify settings:
```bash
processos config set settings.observability.mode full
processos config get settings.pillars
```

Or edit directly (run `processos validate` after manual edits).
""",
        related_topics=["config", "fingerprint"],
    ))

    # claude/ directory explanation
    explainer.register_topic(HelpTopic(
        topic_id="file-claude",
        title="Claude Instructions Directory",
        category="Structure",
        content="""
The `.processos/claude/` directory contains instructions for Claude AI.

## Files

### INSTRUCTIONS.md
Main instructions for Claude when working on this project.
- Your role and context
- Available commands
- Stack-specific guidance

### CONTRACTS.md
Non-negotiable rules that Claude must follow.
- Write allowlist (only `.processos/`)
- Forbidden actions
- Gate policies

### ENTRYPOINT_PROMPT.txt
Copy-paste prompt for terminal-based Claude usage.
- Quick context loading
- Command reference
- Project fingerprint

### PROJECT_CONTEXT.json
Machine-readable project context.
- Stack details
- Policy settings
- Available commands

## Usage

**VSCode with Claude extension:**
Point Claude to `.processos/claude/INSTRUCTIONS.md`

**Terminal (Claude API):**
Copy content from `ENTRYPOINT_PROMPT.txt` as system prompt

**Programmatic:**
Parse `PROJECT_CONTEXT.json` for tooling integration
""",
        related_topics=["files", "init"],
    ))

    # workspaces explanation
    explainer.register_topic(HelpTopic(
        topic_id="file-workspaces",
        title="Workspaces Directory",
        category="Structure",
        content="""
The `.processos/workspaces/` directory contains task execution data.

## Structure

```
.processos/workspaces/
├── ws-abc123/              # Workspace for a specific command
│   ├── MANIFEST.yaml       # Task specification
│   ├── STREAM.md           # Real-time progress output
│   ├── runs/               # Execution runs
│   │   └── run-001/
│   │       ├── telemetry.jsonl
│   │       └── artifacts/
│   └── materials/          # User-provided inputs
└── ws-def456/              # Another workspace
```

## Key Concepts

- **Workspace**: Container for a single command/task
- **Run**: One execution attempt (supports resume)
- **STREAM.md**: Human-readable progress log
- **Materials**: External inputs (API specs, etc.)

## Lazy Creation

Workspaces are created only when you run `processos cmd`.
They are NOT created during `processos init`.

## Cleanup

Old workspaces can be removed:
```bash
rm -rf .processos/workspaces/ws-abc123/
```

Or keep them for audit trail and resume capability.
""",
        related_topics=["workspace", "cmd"],
    ))
