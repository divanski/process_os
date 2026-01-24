"""
ProcessOS CLI

Command-line interface for ProcessOS.
"""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

# Add grandparent directory to path for package imports when running from source
# This allows `from process_os.xxx import yyy` to work when installed in editable mode
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from process_os.bootstrap import (
    Bootstrapper,
    BootstrapResult,
    CommandGateway,
)
from process_os.help import (
    HelpExplainer,
    InteractiveWizard,
    register_core_topics,
    register_error_topics,
    register_file_topics,
)
from process_os.init import (
    PROCESSOS_DIR,
    PROCESSOS_VERSION,
    ConfigManager,
    InitResult,
    ProjectConfig,
    ProjectInitializer,
)
from process_os.init.initializer import detect_ci_environment, is_ci_environment
from process_os.rules import RulesGenerator
from process_os.runtime.telemetry import TERMINAL_EVENTS


# CI mode detection (T052)
_ci_mode = False


def is_ci_mode() -> bool:
    """Check if running in CI mode."""
    global _ci_mode
    return _ci_mode or is_ci_environment()


def set_ci_mode(enabled: bool) -> None:
    """Set CI mode explicitly."""
    global _ci_mode
    _ci_mode = enabled


def _output_json(data: dict) -> None:
    """Output data as JSON (T025)."""
    print(json.dumps(data, indent=2, default=str))


def _output_ci(data: dict) -> None:
    """Output data in CI-friendly format (T052)."""
    # Compact JSON for CI (easier to parse)
    print(json.dumps(data, separators=(',', ':'), default=str))


def cmd_init(args: argparse.Namespace) -> int:
    """Handle init command (T021, T022, T025)."""
    project_root = Path(args.project_root).resolve()
    json_output = getattr(args, "json", False)
    skip_detect = getattr(args, "skip_detect", False)
    stack = getattr(args, "stack", None)

    if not project_root.is_dir():
        if json_output:
            _output_json({"error": f"{project_root} is not a directory", "code": 2})
        else:
            print(f"Error: {project_root} is not a directory", file=sys.stderr)
        return 2

    initializer = ProjectInitializer(project_root)
    output = initializer.init(
        force=args.force,
        project_name=args.name,
        skip_detect=skip_detect,
        stack=stack,
    )

    if output.result == InitResult.ALREADY_EXISTS:
        if json_output:
            _output_json(output.to_dict())
        else:
            print(f"Already initialized: {project_root}")
            print("Use --force to reinitialize")
        return 1

    if output.result != InitResult.SUCCESS:
        if json_output:
            _output_json({"error": output.message, "code": int(output.result.value)})
        else:
            print(f"Error: {output.message}", file=sys.stderr)
        return int(output.result.value)

    # Generate rules pack (claude instructions)
    if output.fingerprint:
        rules_gen = RulesGenerator(project_root)
        rules_gen.generate(output.fingerprint)
    elif output.config:
        # Generate from unified config
        rules_gen = RulesGenerator(project_root)
        rules_gen.generate_from_config(output.config)

    # JSON output (T025)
    if json_output:
        _output_json(output.to_dict())
        return 0

    # Human-readable output
    print(f"Initialized ProcessOS in {project_root}")

    if output.config:
        # Unified config format (v0.8.0+)
        print(f"\nProject: {output.config.project_name}")
        print(f"Binding: {output.config.binding_id}")
        print(f"Fingerprint: {output.config.fingerprint_id}")

        if output.config.stacks:
            print(f"\nDetected Stacks:")
            for stack_cfg in output.config.stacks:
                print(f"  - {stack_cfg.stack_id} ({stack_cfg.confidence})")

        if output.config.frameworks:
            print(f"\nDetected Frameworks:")
            for fw in output.config.frameworks:
                print(f"  - {fw.framework_id} ({fw.stack})")

        # Show detailed fingerprint info if available
        details = output.config.fingerprint_details
        if details:
            print(f"\nStack Details:")
            if details.get("php"):
                php = details["php"]
                v = php.get("constraint") or php.get("version", "unknown")
                print(f"  PHP: {v}")
            if details.get("node"):
                node = details["node"]
                v = node.get("constraint") or node.get("version", "unknown")
                print(f"  Node.js: {v}")
            if details.get("python"):
                py = details["python"]
                v = py.get("constraint") or py.get("version", "unknown")
                print(f"  Python: {v}")
            if details.get("framework"):
                fw = details["framework"]
                resolved = fw.get("resolved") or fw.get("version", "unknown")
                print(f"  Framework: {fw.get('type', 'unknown')} {resolved}")
            if details.get("database"):
                db = details["database"]
                print(f"  Database: {db.get('type', 'unknown')}")
            if details.get("build_tool"):
                bt = details["build_tool"]
                print(f"  Build Tool: {bt.get('name')} {bt.get('version', '')}")
            if details.get("frontend"):
                fe = details["frontend"]
                if fe.get("css"):
                    css = fe["css"]
                    print(f"  CSS: {css.get('name')} {css.get('version', '')}")
                if fe.get("js"):
                    js = fe["js"]
                    print(f"  JS: {js.get('name')} {js.get('version', '')}")
            if details.get("package_manager"):
                print(f"  Package Manager: {details['package_manager']}")
            if details.get("testing"):
                test = details["testing"]
                print(f"  Testing: {test.get('name', 'unknown')} {test.get('version', '')}")
            if details.get("module_system"):
                print(f"  Modules: {details['module_system']}")
            if details.get("features"):
                print(f"  Features: {', '.join(details['features'])}")
            if details.get("key_dependencies"):
                deps = details["key_dependencies"]
                if deps:
                    print(f"  Key Dependencies: {len(deps)} detected")

        print(f"\nCreated:")
        print(f"  .processos/config.yaml")
        print(f"  .processos/claude/")
    else:
        # Legacy format
        print(f"  Binding: {output.binding.binding_id}")
        print(f"  Fingerprint: {output.fingerprint.fingerprint_id}")

        if output.fingerprint.stacks:
            stacks = ", ".join(s["stack_id"] for s in output.fingerprint.stacks)
            print(f"  Detected stacks: {stacks}")

        if output.fingerprint.frameworks:
            frameworks = ", ".join(f["framework_id"] for f in output.fingerprint.frameworks)
            print(f"  Detected frameworks: {frameworks}")

        print(f"\nCreated:")
        print(f"  .processos/fingerprint.yaml")
        print(f"  .processos/binding.yaml")
        print(f"  .processos/claude-rules/")

    print(f"\nNext steps:")
    print(f"  processos cmd \"integrate supplier API\"")
    print(f"  processos interactive")
    print(f"  processos help")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Handle status command (T023)."""
    project_root = Path(args.project_root).resolve()
    json_output = getattr(args, "json", False)

    if not project_root.is_dir():
        if json_output:
            _output_json({"error": f"{project_root} is not a directory", "code": 2})
        else:
            print(f"Error: {project_root} is not a directory", file=sys.stderr)
        return 2

    initializer = ProjectInitializer(project_root)
    output = initializer.status()

    if output.result != InitResult.SUCCESS:
        if json_output:
            _output_json({"initialized": False, "message": output.message})
        else:
            print(f"Not initialized: {project_root}")
            print("Run 'processos init' to initialize")
        return 1

    # JSON output
    if json_output:
        _output_json(output.to_dict())
        return 0

    # Human-readable output
    print(f"ProcessOS Status: {project_root}")
    print(f"  Version: {PROCESSOS_VERSION}")

    if output.config:
        # Unified config format (v0.8.0+)
        print(f"  Project: {output.config.project_name}")
        print(f"  Binding: {output.config.binding_id}")
        print(f"  Fingerprint: {output.config.fingerprint_id}")
        print(f"  Config format: unified (v0.8.0+)")

        if output.config.stacks:
            print(f"\nDetected Stacks:")
            for stack in output.config.stacks:
                print(f"  - {stack.stack_id} ({stack.confidence})")
                if stack.version_hint:
                    print(f"    Version: {stack.version_hint}")

        if output.config.frameworks:
            print(f"\nDetected Frameworks:")
            for fw in output.config.frameworks:
                print(f"  - {fw.framework_id} ({fw.stack})")

        # Show detailed fingerprint info if available
        details = output.config.fingerprint_details
        if details:
            print(f"\nStack Details:")
            if details.get("php"):
                php = details["php"]
                v = php.get("constraint") or php.get("version", "unknown")
                print(f"  PHP: {v}")
            if details.get("node"):
                node = details["node"]
                v = node.get("constraint") or node.get("version", "unknown")
                print(f"  Node.js: {v}")
            if details.get("python"):
                py = details["python"]
                v = py.get("constraint") or py.get("version", "unknown")
                print(f"  Python: {v}")
            if details.get("framework"):
                fw = details["framework"]
                resolved = fw.get("resolved") or fw.get("version", "unknown")
                print(f"  Framework: {fw.get('type', 'unknown')} {resolved}")
            if details.get("database"):
                db = details["database"]
                print(f"  Database: {db.get('type', 'unknown')}")
            if details.get("build_tool"):
                bt = details["build_tool"]
                print(f"  Build Tool: {bt.get('name')} {bt.get('version', '')}")
            if details.get("frontend"):
                fe = details["frontend"]
                if fe.get("css"):
                    css = fe["css"]
                    print(f"  CSS: {css.get('name')} {css.get('version', '')}")
                if fe.get("js"):
                    js = fe["js"]
                    print(f"  JS: {js.get('name')} {js.get('version', '')}")
            if details.get("package_manager"):
                print(f"  Package Manager: {details['package_manager']}")
            if details.get("testing"):
                test = details["testing"]
                print(f"  Testing: {test.get('name', 'unknown')} {test.get('version', '')}")
            if details.get("module_system"):
                print(f"  Modules: {details['module_system']}")
            if details.get("features"):
                print(f"  Features: {', '.join(details['features'])}")
            if details.get("key_dependencies"):
                deps = details["key_dependencies"]
                if deps:
                    print(f"  Key Dependencies: {len(deps)} detected")

        print(f"\nSettings:")
        print(f"  Observability: {output.config.settings.observability.mode}")
        print(f"  Credential sources: {', '.join(output.config.settings.credentials.sources)}")
    else:
        # Legacy format
        print(f"  Binding: {output.binding.binding_id}")
        print(f"  Fingerprint: {output.fingerprint.fingerprint_id}")
        print(f"  Project: {output.binding.project_name}")
        print(f"  Config format: legacy (v0.7.0)")

        if output.fingerprint.stacks:
            print(f"\nDetected Stacks:")
            for stack in output.fingerprint.stacks:
                print(f"  - {stack['stack_id']} ({stack['confidence']})")
                if stack.get("version_hint"):
                    print(f"    Version: {stack['version_hint']}")

        if output.fingerprint.frameworks:
            print(f"\nDetected Frameworks:")
            for fw in output.fingerprint.frameworks:
                print(f"  - {fw['framework_id']} ({fw['stack']})")

    return 0


def cmd_fingerprint(args: argparse.Namespace) -> int:
    """Handle fingerprint command."""
    project_root = Path(args.project_root).resolve()

    if not project_root.is_dir():
        print(f"Error: {project_root} is not a directory", file=sys.stderr)
        return 2

    initializer = ProjectInitializer(project_root)
    output = initializer.refresh_fingerprint()

    if output.result != InitResult.SUCCESS:
        print(f"Error: {output.message}", file=sys.stderr)
        return int(output.result.value)

    # Regenerate rules pack
    if output.fingerprint:
        rules_gen = RulesGenerator(project_root)
        rules_gen.generate(output.fingerprint)

    print(f"Fingerprint refreshed: {output.fingerprint.fingerprint_id}")

    if output.fingerprint.stacks:
        print(f"\nDetected Stacks:")
        for stack in output.fingerprint.stacks:
            print(f"  - {stack['stack_id']} ({stack['confidence']})")

    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Handle bootstrap command."""
    host_root = Path(args.host).resolve()

    if not host_root.is_dir():
        print(f"Error: {host_root} is not a directory", file=sys.stderr)
        return 2

    bootstrapper = Bootstrapper(host_root)
    output = bootstrapper.bootstrap(
        force=args.force,
        project_name=args.name,
    )

    if output.result == BootstrapResult.ALREADY_BOOTSTRAPPED:
        print(f"Already bootstrapped: {host_root}")
        print("Use --force to re-bootstrap")
        return 1

    if output.result != BootstrapResult.SUCCESS:
        print(f"Error: {output.message}", file=sys.stderr)
        return int(output.result.value)

    print(f"Bootstrapped ProcessOS in {host_root}")
    print(f"  Binding: {output.binding_id}")
    print(f"  Fingerprint: {output.fingerprint_id}")
    print(f"\nInstruction Pack:")
    for f in output.instruction_pack_files:
        print(f"  - .processos/claude/{f}")

    print(f"\nTerminal usage:")
    print(f"  Copy-paste: .processos/claude/ENTRYPOINT_PROMPT.txt")
    print(f"\nVSCode usage:")
    print(f"  Point Claude to: .processos/claude/INSTRUCTIONS.md")

    return 0


def _print_stream_content(stream_path: Path, skip_header: bool = True) -> None:
    """
    Print STREAM.md content (Sprint 9.2: deterministic, no JSON parsing).

    Args:
        stream_path: Path to STREAM.md
        skip_header: Whether to skip the header lines
    """
    if not stream_path.exists():
        return

    level_prefixes = {
        "info": "",
        "warn": "⚠️ ",
        "error": "❌ ",
        "blocked": "⏸️ ",
        "success": "✅ ",
    }

    with open(stream_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip header and separator lines
            if not line or line.startswith("#") or line.startswith("|--"):
                continue
            if line.startswith("| Seq |"):
                continue

            # Parse markdown table row: | seq | agent | level | message |
            if line.startswith("|"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    # parts[0] is empty, parts[1] is seq, parts[2] is agent, etc.
                    agent = parts[2]
                    level = parts[3]
                    message = parts[4]
                    prefix = level_prefixes.get(level, "")
                    print(f"{prefix}[{agent}] {message}")


def cmd_execute(args: argparse.Namespace) -> int:
    """Handle cmd command (execute task) with dry-run support (T033, T034)."""
    host_root = Path(getattr(args, "host", ".")).resolve()
    dry_run = getattr(args, "dry_run", False)
    json_output = getattr(args, "json", False)
    use_mock = getattr(args, "mock", False)
    interactive = getattr(args, "interactive", False)
    target_dir = getattr(args, "target_dir", None)

    if not host_root.is_dir():
        if json_output:
            _output_json({"error": f"{host_root} is not a directory", "code": 2})
        else:
            print(f"Error: {host_root} is not a directory", file=sys.stderr)
        return 2

    follow_mode = getattr(args, "follow", False)
    stop_event = threading.Event()
    follow_thread = None

    gateway = CommandGateway(host_root)

    # Start follow thread if --follow is enabled (not in dry-run mode)
    if follow_mode and not dry_run:
        print("Starting execution with live output...")

    # Execute with real pipeline (default) or mock agents
    result = gateway.execute(
        args.command,
        dry_run=dry_run,
        use_dynamic=not use_mock,
        interactive=interactive,
        target_dir=target_dir,
    )

    if not result.success:
        if json_output:
            _output_json({"error": result.error, "code": result.exit_code})
        else:
            print(f"Error: {result.error}", file=sys.stderr)
        return result.exit_code

    # JSON output
    if json_output:
        _output_json(result.to_dict())
        return 0

    # Dry-run output formatting (T034)
    if dry_run:
        print("Dry-run preview (no execution)")
        print(f"\nCommand: {args.command}")
        print(f"Command ID: {result.command_id}")
        print(f"Workspace ID: {result.workspace_id}")
        print(f"\nThis would:")
        print(f"  1. Create workspace: .processos/workspaces/{result.workspace_id}/")
        print(f"  2. Parse task request and generate manifest")
        print(f"  3. Execute agent squad workflow")
        print(f"  4. Write artifacts to workspace")
        print(f"\nTo execute for real, remove the --dry-run flag.")
        return 0

    # Sprint 9.2: Follow mode reads STREAM.md directly (deterministic artifact)
    if follow_mode and result.workspace_id:
        stream_path = host_root / ".processos" / "workspaces" / result.workspace_id / "STREAM.md"
        _print_stream_content(stream_path)
        print()  # Blank line before summary

    print(f"Command executed successfully")
    print(f"  Command ID: {result.command_id}")
    print(f"  Workspace ID: {result.workspace_id}")
    print(f"  Run ID: {result.run_id}")
    print(f"  Run directory: {result.run_dir}")

    # Show workflow state for dynamic integration
    if result.workflow_state:
        print(f"  Workflow State: {result.workflow_state}")

    if result.artifacts:
        print(f"\nArtifacts:")
        for artifact in result.artifacts:
            print(f"  - {artifact}")

    # Show generated files from dynamic integration
    if result.generated_files:
        print(f"\nGenerated Files:")
        for file_path in result.generated_files:
            print(f"  - {file_path}")

    # Show checkpoint path for resume capability
    if result.checkpoint_path:
        print(f"\nCheckpoint: {result.checkpoint_path}")

    if result.telemetry_file and not follow_mode:
        print(f"\nTelemetry: {result.telemetry_file}")

    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle resume command (resume blocked run)."""
    from process_os.runtime.workspace_runner import WorkspaceRunner, RunStatus

    workspace_id = args.workspace
    follow_mode = getattr(args, "follow", False)

    # Determine workspaces root
    if args.host:
        host_root = Path(args.host).resolve()
        workspaces_root = host_root / ".processos" / "workspaces"
    else:
        # Default to current directory
        workspaces_root = Path(".processos") / "workspaces"

    if not workspaces_root.exists():
        print(f"Error: Workspaces directory not found: {workspaces_root}", file=sys.stderr)
        return 2

    runner = WorkspaceRunner(workspaces_root)

    if follow_mode:
        print("Resuming with live output...")

    try:
        state = runner.resume(workspace_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Sprint 9.2: Follow mode reads STREAM.md directly (deterministic artifact)
    if follow_mode:
        workspace_dir = workspaces_root / workspace_id
        stream_path = workspace_dir / "STREAM.md"
        _print_stream_content(stream_path)
        print()  # Blank line before summary

    status_emoji = {
        "succeeded": "✅",
        "failed": "❌",
        "blocked": "⏸️",
        "halted": "🛑",
        "running": "🔄",
    }

    emoji = status_emoji.get(state.status, "❓")
    print(f"{emoji} Resume completed: {state.status}")
    print(f"  Run ID: {state.run_id}")
    print(f"  Status: {state.status}")

    # Sprint 9.1: Show resume lineage
    if state.resumed_from_run_id:
        print(f"  Resumed from: {state.resumed_from_run_id}")
    if state.parent_run_id:
        print(f"  Parent run: {state.parent_run_id}")
    print(f"  Resume attempt: {state.resume_attempt}")

    if state.status == RunStatus.SUCCEEDED.value:
        print(f"  Steps completed: {len(state.completed_steps)}")
        print(f"  Artifacts: {len(state.artifacts)}")
    elif state.status == RunStatus.BLOCKED.value:
        print(f"  Blocked reason: {state.blocked_reason}")
        print(f"  Missing inputs: {', '.join(state.blocked_inputs)}")
    elif state.status == RunStatus.FAILED.value:
        print(f"  Failed step: {state.failed_step}")
        print(f"  Reason: {state.failure_reason}")

    # Show stream file location (unless in follow mode, already printed)
    if not follow_mode:
        workspace_dir = workspaces_root / workspace_id
        stream_file = workspace_dir / "STREAM.md"
        if stream_file.exists():
            print(f"\nProgress stream: {stream_file}")
            print(f"  Tail with: tail -f {stream_file}")

    return 0 if state.status == RunStatus.SUCCEEDED.value else 1


def cmd_interactive(args: argparse.Namespace) -> int:
    """Handle interactive command (T042) - start guided workflow."""
    workflow_id = getattr(args, "workflow", None)
    list_workflows = getattr(args, "list", False)

    # Create wizard (workflows are dynamically generated)
    wizard = InteractiveWizard()

    # List available workflows
    if list_workflows:
        workflows = wizard.list_workflows()
        if not workflows:
            print("No workflows available.")
            return 0

        print("Available workflows:\n")
        for wf in workflows:
            print(f"  {wf.id}")
            print(f"    {wf.title}")
            print(f"    {wf.description}\n")

        print(f"Start a workflow: processos interactive <workflow_id>")
        return 0

    # Start specific workflow or show menu
    if workflow_id:
        try:
            step = wizard.start_workflow(workflow_id)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("\nAvailable workflows:")
            for wf in wizard.list_workflows():
                print(f"  - {wf.id}: {wf.title}")
            return 1
    else:
        # Show workflow menu
        workflows = wizard.list_workflows()
        if not workflows:
            print("No workflows available.")
            return 0

        print("ProcessOS Interactive Mode\n")
        print("Available workflows:")
        for i, wf in enumerate(workflows, 1):
            print(f"  {i}. {wf.title}")
            print(f"     {wf.description}")
        print()

        # Prompt for selection
        try:
            choice = input("Select workflow (number or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                return 0

            idx = int(choice) - 1
            if 0 <= idx < len(workflows):
                step = wizard.start_workflow(workflows[idx].id)
            else:
                print("Invalid selection.")
                return 1
        except (ValueError, EOFError):
            print("Invalid input.")
            return 1

    # Run interactive wizard loop
    while step:
        # Display current step
        print()
        print(wizard.format_step(step))

        # Handle step based on type
        from process_os.help import WizardStepType

        if step.step_type == WizardStepType.INFO:
            input("\nPress Enter to continue...")
            step = wizard.submit_input(None)

        elif step.step_type == WizardStepType.INPUT:
            try:
                value = input().strip()
                if value == "":
                    value = step.input_default or ""
                step = wizard.submit_input(value)
            except EOFError:
                wizard.cancel()
                return 1

        elif step.step_type == WizardStepType.CHOICE:
            try:
                choice = input("\nEnter choice (number or 'b' for back): ").strip()
                if choice.lower() == 'b' and step.previous_step:
                    step = wizard.go_back()
                    continue

                idx = int(choice) - 1
                if 0 <= idx < len(step.choices):
                    step = wizard.submit_input(step.choices[idx].key)
                else:
                    print("Invalid choice. Please try again.")
            except (ValueError, EOFError):
                print("Invalid input. Please enter a number.")

        elif step.step_type == WizardStepType.CONFIRM:
            try:
                confirm = input().strip().lower()
                if confirm in ('y', 'yes'):
                    step = wizard.submit_input(True)
                elif confirm in ('n', 'no'):
                    step = wizard.go_back()
                else:
                    print("Please enter 'y' or 'n'.")
            except EOFError:
                wizard.cancel()
                return 1

        elif step.step_type == WizardStepType.EXECUTE:
            print("\nExecuting...")
            # In a real implementation, this would run the action
            step = wizard.submit_input(None)

        elif step.step_type == WizardStepType.COMPLETE:
            print()
            break

    # Show final progress
    progress = wizard.get_progress()
    if progress.get("active"):
        print(f"\nWorkflow '{progress['workflow_title']}' completed.")
        print(f"Progress: {progress['progress_percent']}%")

        if progress.get("inputs"):
            print("\nCollected inputs:")
            for key, value in progress["inputs"].items():
                print(f"  {key}: {value}")

    return 0


def cmd_help(args: argparse.Namespace) -> int:
    """Handle help command (T043) - display help topics."""
    topic_id = getattr(args, "topic", None)
    list_topics = getattr(args, "list", False)
    json_output = getattr(args, "json", False)

    # Create explainer with registered topics
    explainer = HelpExplainer()
    register_core_topics(explainer)
    register_error_topics(explainer)
    register_file_topics(explainer)

    # List all topics
    if list_topics:
        topics = explainer.list_topics()

        if json_output:
            _output_json({
                "topics": [
                    {"id": t.topic_id, "title": t.title, "category": t.category}
                    for t in topics
                ]
            })
            return 0

        print("Available help topics:\n")

        # Group by category
        by_category: dict = {}
        for t in topics:
            cat = t.category or "General"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(t)

        for category, cat_topics in sorted(by_category.items()):
            print(f"{category}:")
            for t in cat_topics:
                print(f"  {t.topic_id:20} {t.title}")
            print()

        print("View a topic: processos help <topic>")
        return 0

    # Show specific topic or overview
    if topic_id:
        topic = explainer.get_topic(topic_id)
        if not topic:
            print(f"Error: Unknown topic '{topic_id}'", file=sys.stderr)
            print("\nTry 'processos help --list' to see available topics.")
            return 1

        if json_output:
            _output_json({
                "id": topic.topic_id,
                "title": topic.title,
                "category": topic.category,
                "content": topic.content,
                "related": topic.related_topics,
                "see_also": topic.see_also,
            })
            return 0

        # Format topic for display
        print(f"# {topic.title}\n")
        print(topic.content)

        if topic.related_topics:
            print(f"\nRelated topics: {', '.join(topic.related_topics)}")

        if topic.see_also:
            print(f"\nSee also:")
            for url in topic.see_also:
                print(f"  {url}")

        return 0

    # Default: show overview
    if json_output:
        _output_json({
            "version": PROCESSOS_VERSION,
            "commands": [
                "init", "status", "cmd", "interactive", "help",
                "config", "validate", "fingerprint", "resume", "bootstrap"
            ]
        })
        return 0

    print(f"""ProcessOS Help
Version: {PROCESSOS_VERSION}

ProcessOS is an AI-driven integration engine that dynamically handles
any integration type without hardcoded configurations.

Quick Start:
  processos init              Initialize ProcessOS in current directory
  processos cmd "task"        Execute a task via the command gateway
  processos interactive       Start guided workflow wizard
  processos help <topic>      Get help on a specific topic

Common Topics:
  processos help init         Learn about project initialization
  processos help cmd          Learn about the command gateway
  processos help playbook     Learn about dynamic playbooks
  processos help workspace    Learn about workspaces

List all topics:
  processos help --list

For more information, visit: https://github.com/processos/processos
""")

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Handle config command (T048) - view/modify configuration."""
    project_root = Path(getattr(args, "project_root", ".")).resolve()
    json_output = getattr(args, "json", False)
    action = getattr(args, "action", "show")
    path = getattr(args, "path", None)
    value = getattr(args, "value", None)

    config_manager = ConfigManager(project_root)

    if not config_manager.is_initialized:
        if json_output:
            _output_json({"error": "Project not initialized", "code": 1})
        else:
            print("Error: Project not initialized. Run 'processos init' first.", file=sys.stderr)
        return 1

    # Show full config
    if action == "show":
        config = config_manager.load()
        if config is None:
            print("Error: Failed to load configuration", file=sys.stderr)
            return 1

        if json_output:
            _output_json(config.to_dict())
            return 0

        print(config.to_yaml())
        return 0

    # Get specific value
    if action == "get":
        if not path:
            print("Error: Path required for 'get' action", file=sys.stderr)
            return 1

        try:
            result = config_manager.get_value(path)
            if json_output:
                _output_json({"path": path, "value": result})
            else:
                if isinstance(result, (dict, list)):
                    print(json.dumps(result, indent=2))
                else:
                    print(result)
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Set specific value
    if action == "set":
        if not path or value is None:
            print("Error: Path and value required for 'set' action", file=sys.stderr)
            return 1

        try:
            # Try to parse value as JSON, fall back to string
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value

            config = config_manager.update_setting(path, parsed_value)
            if json_output:
                _output_json({"path": path, "value": parsed_value, "updated": True})
            else:
                print(f"Updated {path} = {parsed_value}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    print(f"Error: Unknown action '{action}'", file=sys.stderr)
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command (T049) - validate configuration."""
    project_root = Path(getattr(args, "project_root", ".")).resolve()
    json_output = getattr(args, "json", False)
    fix = getattr(args, "fix", False)

    config_manager = ConfigManager(project_root)
    result = config_manager.validate(fix=fix)

    if json_output:
        _output_json(result.to_dict())
        return 0 if result.valid else 1

    print(result.format())

    if not result.valid:
        print("\nRun 'processos validate --fix' to automatically fix fixable issues.")

    return 0 if result.valid else 1


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="processos",
        description="ProcessOS - AI Agent Squad Orchestration",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ProcessOS {PROCESSOS_VERSION}",
    )
    # T052: CI mode flag
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Force CI mode (structured output, no color, no prompts)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command (T021, T022, T025)
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize ProcessOS in a project",
    )
    init_parser.add_argument(
        "--project-root",
        "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )
    init_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing initialization",
    )
    init_parser.add_argument(
        "--name",
        "-n",
        help="Project name (default: directory name)",
    )
    # T022: --skip-detect and --pillar flags
    init_parser.add_argument(
        "--skip-detect",
        action="store_true",
        help="Skip auto-detection, use --stack to specify manually",
    )
    init_parser.add_argument(
        "--stack",
        "-s",
        help="Manually specify stack (e.g., 'python', 'node', 'php')",
    )
    # T025: JSON output
    init_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    init_parser.set_defaults(func=cmd_init)

    # status command (T023)
    status_parser = subparsers.add_parser(
        "status",
        help="Show ProcessOS status for a project",
    )
    status_parser.add_argument(
        "--project-root",
        "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    status_parser.set_defaults(func=cmd_status)

    # fingerprint command
    fp_parser = subparsers.add_parser(
        "fingerprint",
        help="Re-run stack fingerprint detection",
    )
    fp_parser.add_argument(
        "--project-root",
        "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )
    fp_parser.set_defaults(func=cmd_fingerprint)

    # bootstrap command (kept for backward compatibility, T024)
    # Note: 'init' is the preferred command in v0.8.0+
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Bootstrap ProcessOS into a host project (alias for 'init --project-root')",
    )
    bootstrap_parser.add_argument(
        "--host",
        "-H",
        required=True,
        help="Host project root directory",
    )
    bootstrap_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing bootstrap",
    )
    bootstrap_parser.add_argument(
        "--name",
        "-n",
        help="Project name (default: directory name)",
    )
    bootstrap_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    bootstrap_parser.set_defaults(func=cmd_bootstrap)

    # cmd command (execute task) with dry-run support (T033)
    cmd_parser = subparsers.add_parser(
        "cmd",
        help="Execute a command through the gateway",
    )
    cmd_parser.add_argument(
        "command",
        help="Command to execute (e.g., 'integrate supplier API')",
    )
    cmd_parser.add_argument(
        "--host",
        "-H",
        default=".",
        help="Project root directory (default: current directory)",
    )
    cmd_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be executed without running",
    )
    cmd_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    cmd_parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow agent output in real-time (Sprint 9.1)",
    )
    cmd_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock agents instead of real IntegrationRunner pipeline",
    )
    cmd_parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Enable interactive prompts for user input during integration",
    )
    cmd_parser.add_argument(
        "--target-dir",
        "-t",
        help="Subdirectory to limit discovery scope (for large projects)",
    )
    cmd_parser.set_defaults(func=cmd_execute)

    # resume command (resume blocked run)
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a blocked run after providing missing materials",
    )
    resume_parser.add_argument(
        "--workspace",
        "-w",
        required=True,
        help="Workspace ID to resume (e.g., 'ws-abc123')",
    )
    resume_parser.add_argument(
        "--host",
        "-H",
        help="Host project root directory (optional)",
    )
    resume_parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow agent output in real-time (Sprint 9.1)",
    )
    resume_parser.set_defaults(func=cmd_resume)

    # interactive command (T042)
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Start interactive workflow wizard",
    )
    interactive_parser.add_argument(
        "workflow",
        nargs="?",
        help="Workflow ID to start (optional, shows menu if not provided)",
    )
    interactive_parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available workflows",
    )
    interactive_parser.set_defaults(func=cmd_interactive)

    # help command (T043)
    help_parser = subparsers.add_parser(
        "help",
        help="Display help topics and documentation",
    )
    help_parser.add_argument(
        "topic",
        nargs="?",
        help="Topic ID to display (optional, shows overview if not provided)",
    )
    help_parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all available help topics",
    )
    help_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    help_parser.set_defaults(func=cmd_help)

    # config command (T048)
    config_parser = subparsers.add_parser(
        "config",
        help="View or modify project configuration",
    )
    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "get", "set"],
        default="show",
        help="Action: show (default), get <path>, set <path> <value>",
    )
    config_parser.add_argument(
        "path",
        nargs="?",
        help="Configuration path (e.g., 'settings.observability.mode')",
    )
    config_parser.add_argument(
        "value",
        nargs="?",
        help="Value to set (for 'set' action)",
    )
    config_parser.add_argument(
        "--project-root",
        "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )
    config_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    config_parser.set_defaults(func=cmd_config)

    # validate command (T049)
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate project configuration",
    )
    validate_parser.add_argument(
        "--project-root",
        "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )
    validate_parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix fixable issues",
    )
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # T052: Handle CI mode
    if getattr(args, "ci", False):
        set_ci_mode(True)

    # Auto-detect CI environment
    ci_provider = detect_ci_environment()
    if ci_provider:
        set_ci_mode(True)
        # In CI, output detection info to stderr (not stdout which may be parsed)
        print(f"::processos:: CI detected: {ci_provider}", file=sys.stderr)

    if not args.command:
        if is_ci_mode():
            # In CI mode, no command = error
            _output_ci({"error": "No command specified", "code": 1})
            return 1
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
