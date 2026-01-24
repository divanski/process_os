"""
ProcessOS Error Help Topics

Help topics for error codes with remediation guidance.
"""

from ..explainer import HelpCategory, HelpExplainer, HelpTopic


def register_error_topics(explainer: HelpExplainer) -> None:
    """Register error help topics with the explainer."""

    # E001 - Project not initialized
    explainer.register(HelpTopic(
        id="error:E001",
        title="Project Not Initialized",
        category=HelpCategory.ERROR,
        summary="ProcessOS has not been initialized in this project.",
        description="""
**Error E001**: The project directory doesn't have ProcessOS configuration.

This happens when you try to run ProcessOS commands in a directory that
hasn't been initialized yet.
""",
        error_codes=["E001"],
        remediation="""
Initialize ProcessOS in your project:

```bash
cd /path/to/your/project
processos init
```

If you want to specify options:
```bash
processos init --name "My Project" --pillar courier
```
""",
        related=["init", "status"],
    ))

    # E002 - Already initialized
    explainer.register(HelpTopic(
        id="error:E002",
        title="Already Initialized",
        category=HelpCategory.ERROR,
        summary="ProcessOS is already initialized in this project.",
        description="""
**Error E002**: This project already has ProcessOS configuration.

The `.processos/` directory already exists with configuration files.
""",
        error_codes=["E002"],
        remediation="""
Options:

1. **View current status**:
   ```bash
   processos status
   ```

2. **Reinitialize** (overwrites existing):
   ```bash
   processos init --force
   ```

3. **Remove and start fresh**:
   ```bash
   rm -rf .processos/
   processos init
   ```
""",
        related=["init", "status"],
    ))

    # E020 - API key not found
    explainer.register(HelpTopic(
        id="error:E020",
        title="API Key Not Found",
        category=HelpCategory.ERROR,
        summary="Required API credentials are missing.",
        description="""
**Error E020**: ProcessOS couldn't find required API credentials.

AI-powered tasks require an Anthropic API key to communicate with Claude.
""",
        error_codes=["E020"],
        remediation="""
Set your API key using one of these methods:

1. **Environment variable** (recommended):
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **Create .env file** in project root:
   ```bash
   echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
   ```

3. **System keychain** (requires keyring package):
   ```bash
   pip install keyring
   python -c "import keyring; keyring.set_password('processos', 'ANTHROPIC_API_KEY', 'sk-ant-...')"
   ```

Get an API key at: https://console.anthropic.com/
""",
        related=["credentials", "init"],
    ))

    # E040 - No stack detected
    explainer.register(HelpTopic(
        id="error:E040",
        title="No Stack Detected",
        category=HelpCategory.ERROR,
        summary="ProcessOS couldn't detect the project's technology stack.",
        description="""
**Error E040**: No recognizable technology stack was found.

ProcessOS looks for common configuration files like:
- `package.json` (Node.js)
- `requirements.txt`, `pyproject.toml` (Python)
- `composer.json` (PHP)
- `Gemfile` (Ruby)
- `pom.xml`, `build.gradle` (Java)
""",
        error_codes=["E040"],
        remediation="""
Options:

1. **Manually specify stack**:
   ```bash
   processos init --skip-detect --stack python
   ```

2. **Add configuration files** to your project:
   - For Python: Create `pyproject.toml` or `requirements.txt`
   - For Node: Create `package.json`
   - For PHP: Create `composer.json`

3. **Check project structure**: Ensure you're in the correct directory.
""",
        related=["fingerprint", "init"],
    ))

    # E061 - Task blocked
    explainer.register(HelpTopic(
        id="error:E061",
        title="Task Blocked",
        category=HelpCategory.ERROR,
        summary="A task is waiting for additional input to proceed.",
        description="""
**Error E061**: The task needs something before it can continue.

This usually means:
- Missing required information
- Files need to be provided
- A decision needs to be made
""",
        error_codes=["E061"],
        remediation="""
1. **Check what's needed**:
   ```bash
   processos status
   ```

2. **Provide missing materials** to the workspace

3. **Resume the task**:
   ```bash
   processos resume --workspace ws-abc123
   ```

Common blocking reasons:
- API documentation URL needed
- Credentials required for external service
- Design decision required
""",
        related=["resume", "workspace", "status"],
    ))

    # E100 - Network unavailable
    explainer.register(HelpTopic(
        id="error:E100",
        title="Network Unavailable",
        category=HelpCategory.ERROR,
        summary="Network connectivity is required for this operation.",
        description="""
**Error E100**: AI-powered tasks require network access.

Some commands work offline:
- `processos init`
- `processos status`
- `processos help`
- `processos config`

Commands requiring network:
- `processos cmd "..."`
- `processos resume`
""",
        error_codes=["E100"],
        remediation="""
1. **Check network connectivity**

2. **Use offline commands** if possible:
   ```bash
   processos status
   processos help
   ```

3. **Try again** when network is available
""",
        related=["cmd", "resume"],
    ))

    # Credentials topic (not an error, but related)
    explainer.register(HelpTopic(
        id="credentials",
        title="Credential Management",
        category=HelpCategory.CONCEPT,
        summary="How ProcessOS manages API keys and secrets.",
        description="""
ProcessOS checks for credentials in this order:

1. **Environment variables** (highest priority)
2. **System keychain** (if keyring installed)
3. **Local .env file** (lowest priority)

## Required Credentials

- `ANTHROPIC_API_KEY`: For AI-powered tasks

## Security Notes

- Never commit credentials to version control
- Add `.env` to `.gitignore`
- Environment variables are preferred for CI/CD

## Configuration

Set credential sources in config.yaml:
```yaml
settings:
  credentials:
    sources: [env, keychain, file]
```
""",
        examples=[
            "export ANTHROPIC_API_KEY=sk-ant-...",
            'echo "ANTHROPIC_API_KEY=..." >> .env',
        ],
        related=["init", "error:E020"],
    ))
