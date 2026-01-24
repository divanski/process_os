"""
ProcessOS Rules Generator

Generates Claude rules packs based on detected stack fingerprint.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from process_os.init.binding import PROCESSOS_DIR

if TYPE_CHECKING:
    from process_os.init.config import ProjectConfig
from process_os.stack_fingerprint import StackFingerprint


# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


class RulesGenerator:
    """
    Generates Claude rules pack for a project.

    Rules are tailored to the detected technology stack.
    Supports both legacy fingerprint and unified config (v0.8.0+).
    """

    def __init__(self, project_root: Path, use_new_dir: bool = False):
        """
        Initialize generator.

        Args:
            project_root: Path to project root
            use_new_dir: Use 'claude' instead of 'claude-rules' directory
        """
        self.project_root = Path(project_root).resolve()
        # v0.8.0+: Use 'claude' directory instead of 'claude-rules'
        dir_name = "claude" if use_new_dir else "claude-rules"
        self.rules_dir = self.project_root / PROCESSOS_DIR / dir_name

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, fingerprint: StackFingerprint) -> Path:
        """
        Generate rules pack based on fingerprint.

        Args:
            fingerprint: Stack fingerprint

        Returns:
            Path to rules directory
        """
        # Create rules directory
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        # Build context for templates
        context = self._build_context(fingerprint)

        # Generate index file
        self._render_template("_index.md.j2", "_index.md", context)

        # Generate project context rules
        self._render_template("project-context.md.j2", "project-context.md", context)

        # Generate stack-specific rules
        for stack in fingerprint.stacks:
            stack_id = stack["stack_id"]
            template_name = f"stack-{stack_id}.md.j2"

            if self._template_exists(template_name):
                output_name = f"stack-{stack_id}.md"
                self._render_template(template_name, output_name, context)

        # Generate framework-specific rules
        for framework in fingerprint.frameworks:
            framework_id = framework["framework_id"]
            template_name = f"framework-{framework_id}.md.j2"

            if self._template_exists(template_name):
                output_name = f"framework-{framework_id}.md"
                self._render_template(template_name, output_name, context)

        return self.rules_dir

    def generate_from_config(self, config: "ProjectConfig") -> Path:
        """
        Generate rules pack based on unified config (v0.8.0+).

        Args:
            config: Project configuration

        Returns:
            Path to rules directory
        """
        # Use new 'claude' directory for unified config
        self.rules_dir = self.project_root / PROCESSOS_DIR / "claude"
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        # Build context for templates
        context = self._build_context_from_config(config)

        # Generate index file
        self._render_template("_index.md.j2", "_index.md", context)

        # Generate project context rules
        self._render_template("project-context.md.j2", "project-context.md", context)

        # Generate stack-specific rules
        for stack in config.stacks:
            stack_id = stack.stack_id
            template_name = f"stack-{stack_id}.md.j2"

            if self._template_exists(template_name):
                output_name = f"stack-{stack_id}.md"
                self._render_template(template_name, output_name, context)

        # Generate framework-specific rules
        for framework in config.frameworks:
            framework_id = framework.framework_id
            template_name = f"framework-{framework_id}.md.j2"

            if self._template_exists(template_name):
                output_name = f"framework-{framework_id}.md"
                self._render_template(template_name, output_name, context)

        # Generate INSTRUCTIONS.md for VSCode integration
        self._render_template("INSTRUCTIONS.md.j2", "INSTRUCTIONS.md", context)

        return self.rules_dir

    def _build_context(self, fingerprint: StackFingerprint) -> Dict[str, Any]:
        """Build template context from fingerprint."""
        return {
            "fingerprint": fingerprint.to_dict(),
            "stacks": fingerprint.stacks,
            "frameworks": fingerprint.frameworks,
            "stack_ids": fingerprint.get_stack_ids(),
            "framework_ids": fingerprint.get_framework_ids(),
            "project_root": str(self.project_root),
            "has_python": fingerprint.has_stack("python"),
            "has_node": fingerprint.has_stack("node"),
            "has_rust": fingerprint.has_stack("rust"),
            "has_go": fingerprint.has_stack("go"),
        }

    def _build_context_from_config(self, config: "ProjectConfig") -> Dict[str, Any]:
        """Build template context from unified config."""
        stack_ids = [s.stack_id for s in config.stacks]
        framework_ids = [f.framework_id for f in config.frameworks]

        return {
            "config": config.to_dict(),
            "stacks": [s.to_dict() for s in config.stacks],
            "frameworks": [f.to_dict() for f in config.frameworks],
            "stack_ids": stack_ids,
            "framework_ids": framework_ids,
            "project_root": str(self.project_root),
            "project_name": config.project_name,
            "has_python": "python" in stack_ids,
            "has_node": "node" in stack_ids,
            "has_rust": "rust" in stack_ids,
            "has_go": "go" in stack_ids,
            "has_php": "php" in stack_ids,
            "has_ruby": "ruby" in stack_ids,
            "has_java": "java" in stack_ids,
        }

    def _template_exists(self, name: str) -> bool:
        """Check if template exists."""
        return (TEMPLATES_DIR / name).exists()

    def _render_template(
        self,
        template_name: str,
        output_name: str,
        context: Dict[str, Any],
    ) -> Path:
        """Render a template to the rules directory."""
        template = self.env.get_template(template_name)
        content = template.render(**context)

        output_path = self.rules_dir / output_name
        output_path.write_text(content, encoding="utf-8")

        return output_path


def generate_rules(
    project_root: Path,
    fingerprint: StackFingerprint,
) -> Path:
    """
    Convenience function to generate rules.

    Args:
        project_root: Path to project root
        fingerprint: Stack fingerprint

    Returns:
        Path to rules directory
    """
    generator = RulesGenerator(project_root)
    return generator.generate(fingerprint)
