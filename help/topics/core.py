"""
ProcessOS Core Help Topics

Help topics for core ProcessOS concepts: binding, playbook, workspace.
"""

from ..explainer import HelpCategory, HelpExplainer, HelpTopic


def register_core_topics(explainer: HelpExplainer) -> None:
    """Register core help topics with the explainer."""

    # Binding topic
    explainer.register(HelpTopic(
        id="binding",
        title="Project Binding",
        category=HelpCategory.CONCEPT,
        summary="Links ProcessOS to your project with detected stack information.",
        description="""
A **binding** connects ProcessOS to your project. It stores:

- **binding_id**: Unique identifier for this project-ProcessOS connection
- **fingerprint_id**: Reference to detected technology stack
- **project_name**: Your project's name
- **project_context**: Discovered project architecture and patterns

The binding is created during `processos init` and stored in `.processos/config.yaml`.

## How It Works

1. ProcessOS scans your project for technology markers
2. Creates a fingerprint of detected stacks/frameworks
3. Generates a deterministic binding ID from the fingerprint
4. Stores configuration for future commands

## When to Refresh

Run `processos fingerprint` if you:
- Add new frameworks or languages
- Change project structure significantly
- Want to update detected versions
""",
        examples=[
            "processos init                    # Create new binding",
            "processos status                  # View current binding",
            "processos fingerprint             # Refresh detection",
        ],
        related=["fingerprint", "init", "config"],
        file_patterns=["config.yaml", "binding.yaml"],
    ))

    # Fingerprint topic
    explainer.register(HelpTopic(
        id="fingerprint",
        title="Stack Fingerprint",
        category=HelpCategory.CONCEPT,
        summary="Detected technology stack and frameworks in your project.",
        description="""
A **fingerprint** captures the detected technology stack in your project:

- **Language stacks**: Python, Node.js, PHP, Ruby, Java, etc.
- **Frameworks**: Django, Laravel, Express, Rails, Spring Boot, etc.
- **Confidence levels**: How certain the detection is (high/medium/low)
- **Version hints**: Detected version information when available

## Detection Process

ProcessOS uses multiple signals for detection:
1. **Primary files**: Must-have files (e.g., `package.json` for Node)
2. **Secondary files**: Boost confidence (e.g., `routes/` directory)
3. **Content patterns**: Regex matches in files
4. **Dependencies**: Package manager dependency lists

## Confidence Levels

- **High**: Multiple strong signals found
- **Medium**: Primary signals found
- **Low**: Some indicators but uncertain
""",
        examples=[
            "processos fingerprint             # Refresh fingerprint",
            "processos status                  # View detected stack",
            "processos init --stack python    # Override detection",
        ],
        related=["binding", "init", "status"],
    ))

    # Workspace topic
    explainer.register(HelpTopic(
        id="workspace",
        title="Task Workspace",
        category=HelpCategory.CONCEPT,
        summary="Isolated environment where ProcessOS executes tasks.",
        description="""
A **workspace** is created for each task you run. It contains:

- **manifest.yaml**: Task definition and configuration
- **STREAM.md**: Real-time progress log
- **artifacts/**: Generated files (reports, mappings, etc.)
- **runs/**: Execution history with telemetry

## Workspace Lifecycle

1. **Created**: When you run `processos cmd "..."`
2. **Running**: Agents execute steps, write to STREAM.md
3. **Completed**: Artifacts generated, run recorded
4. **Blocked**: Waiting for user input (can be resumed)

## Workspace Location

```
.processos/workspaces/
  ws-abc123/           # Workspace ID
    manifest.yaml      # Task definition
    STREAM.md          # Progress log
    artifacts/         # Generated files
    runs/              # Execution history
```

## Resuming Blocked Workspaces

If a task needs input:
```bash
processos status                    # See blocked workspace
processos resume --workspace ws-abc123
```
""",
        examples=[
            "processos cmd \"integrate DHL\"   # Creates workspace",
            "processos status                  # List workspaces",
            "processos resume -w ws-abc123    # Resume blocked",
        ],
        related=["cmd", "resume", "status"],
        file_patterns=["manifest.yaml", "STREAM.md"],
    ))

    # Playbook topic
    explainer.register(HelpTopic(
        id="playbook",
        title="Dynamic Playbook",
        category=HelpCategory.CONCEPT,
        summary="Dynamically generated workflow for accomplishing integration tasks.",
        description="""
A **playbook** defines how ProcessOS accomplishes a task:

- **Steps**: Ordered sequence of agent actions
- **Gates**: Checkpoints requiring validation
- **Artifacts**: Expected outputs at each stage

## How Playbooks Work

When you run a command:
1. ProcessOS analyzes your intent using AI
2. Discovers your project structure automatically
3. Dynamically generates a playbook for your specific integration
4. Composes a squad of agents based on requirements
5. Executes steps with validation gates
6. Produces code tailored to your project's architecture

## Dynamic Generation

ProcessOS creates playbooks on-the-fly based on:
- Your natural language request
- Detected project patterns and conventions
- External API requirements
- Best practices for your framework

No hardcoded playbooks - every workflow is customized.
""",
        examples=[
            "processos cmd \"integrate supplier API\"",
            "processos interactive             # Step through playbook",
        ],
        related=["workspace", "cmd", "agent"],
    ))

    # Config topic
    explainer.register(HelpTopic(
        id="config",
        title="Configuration",
        category=HelpCategory.ARTIFACT,
        summary="ProcessOS configuration file (.processos/config.yaml).",
        description="""
The **config.yaml** file contains all ProcessOS settings:

```yaml
version: "1.0.0"
project:
  name: "my-project"
  root: "."
binding:
  binding_id: "bind-abc123"
  processos_version: "0.8.0"
fingerprint:
  fingerprint_id: "fp-def456"
  stacks:
    - stack_id: python
      confidence: high
  frameworks:
    - framework_id: django
      stack: python
      confidence: high
settings:
  observability:
    mode: minimal    # minimal | full | silent
  credentials:
    sources: [env, keychain, file]
```

## Editing Configuration

```bash
processos config                              # View config
processos config settings.observability.mode full  # Set value
processos validate                            # Validate config
processos validate --fix                      # Auto-fix issues
```
""",
        examples=[
            "processos config                  # View configuration",
            "processos validate                # Validate config",
        ],
        related=["init", "status", "validate"],
        file_patterns=["config.yaml"],
    ))

    # Init command topic
    explainer.register(HelpTopic(
        id="init",
        title="init Command",
        category=HelpCategory.COMMAND,
        summary="Initialize ProcessOS in a project directory.",
        description="""
The `init` command sets up ProcessOS in your project:

```bash
processos init [OPTIONS]
```

## Options

- `-p, --project-root PATH`: Project directory (default: current)
- `-f, --force`: Overwrite existing initialization
- `-n, --name NAME`: Project name (default: directory name)
- `--skip-detect`: Skip auto-detection
- `-s, --stack STACK`: Manually specify stack
- `--json`: Output in JSON format

## What It Creates

```
.processos/
  config.yaml    # Unified configuration
  claude/        # AI instructions
```

## Examples

```bash
processos init                          # Auto-detect everything
processos init --stack python           # Override stack
processos init --json                   # JSON output
```
""",
        examples=[
            "processos init",
            "processos init --force",
            "processos init --stack python",
        ],
        related=["status", "fingerprint", "config"],
    ))

    # Cmd command topic
    explainer.register(HelpTopic(
        id="cmd",
        title="cmd Command",
        category=HelpCategory.COMMAND,
        summary="Execute a task through the ProcessOS gateway.",
        description="""
The `cmd` command executes tasks:

```bash
processos cmd "COMMAND" [OPTIONS]
```

## Options

- `-H, --host PATH`: Project directory (default: current)
- `--dry-run`: Preview without executing
- `--json`: Output in JSON format
- `-f, --follow`: Follow output in real-time

## Task Syntax

Natural language commands work best:
- "integrate supplier AutoParts API"
- "map API endpoints from swagger.json"
- "integrate payment gateway Stripe"

## Examples

```bash
processos cmd "integrate supplier API"
processos cmd "integrate API" --dry-run  # Preview
processos cmd "map endpoints" --follow   # Live output
```
""",
        examples=[
            'processos cmd "integrate supplier API"',
            'processos cmd "validate integration" --dry-run',
        ],
        related=["workspace", "resume", "status"],
    ))

    # Status command topic
    explainer.register(HelpTopic(
        id="status",
        title="status Command",
        category=HelpCategory.COMMAND,
        summary="Show ProcessOS status for a project.",
        description="""
The `status` command shows project state:

```bash
processos status [OPTIONS]
```

## Options

- `-p, --project-root PATH`: Project directory
- `--json`: Output in JSON format

## Output Includes

- ProcessOS version
- Project name and binding ID
- Detected stacks and frameworks
- Active pillars
- Configuration settings

## Examples

```bash
processos status                  # Current directory
processos status -p /path/to/project
processos status --json          # Machine-readable
```
""",
        examples=[
            "processos status",
            "processos status --json",
        ],
        related=["init", "config", "fingerprint"],
    ))
