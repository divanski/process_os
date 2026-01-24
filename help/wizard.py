"""
ProcessOS Interactive Wizard

State machine for guiding users through workflows step-by-step.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .session import InteractiveSession, SessionState


class WizardStepType(Enum):
    """Type of wizard step."""
    INFO = "info"           # Display information
    INPUT = "input"         # Collect user input
    CHOICE = "choice"       # Present choices
    CONFIRM = "confirm"     # Confirm before proceeding
    EXECUTE = "execute"     # Execute an action
    COMPLETE = "complete"   # Workflow complete


@dataclass
class WizardChoice:
    """A choice in a choice step."""
    key: str
    label: str
    description: str = ""
    next_step: Optional[str] = None


@dataclass
class WizardStep:
    """A step in the wizard workflow."""
    id: str
    title: str
    step_type: WizardStepType
    message: str

    # For input steps
    input_key: Optional[str] = None
    input_prompt: Optional[str] = None
    input_default: Optional[str] = None

    # For choice steps
    choices: List[WizardChoice] = field(default_factory=list)

    # Navigation
    next_step: Optional[str] = None
    previous_step: Optional[str] = None

    # For execute steps
    action: Optional[Callable] = None

    # Help integration
    help_topic: Optional[str] = None


@dataclass
class WizardWorkflow:
    """A complete wizard workflow."""
    id: str
    title: str
    description: str
    steps: Dict[str, WizardStep] = field(default_factory=dict)
    start_step: str = ""

    def add_step(self, step: WizardStep) -> None:
        """Add a step to the workflow."""
        self.steps[step.id] = step
        if not self.start_step:
            self.start_step = step.id


class InteractiveWizard:
    """
    Manages interactive wizard workflows.

    Provides step-by-step guidance through complex tasks,
    collecting input and displaying help along the way.
    """

    def __init__(self, session: Optional[InteractiveSession] = None):
        """
        Initialize the wizard.

        Args:
            session: Existing session to resume, or None for new
        """
        self.session = session or InteractiveSession()
        self.workflows: Dict[str, WizardWorkflow] = {}
        self.current_workflow: Optional[WizardWorkflow] = None
        self.current_step: Optional[WizardStep] = None

    def register_workflow(self, workflow: WizardWorkflow) -> None:
        """Register a workflow with the wizard."""
        self.workflows[workflow.id] = workflow

    def list_workflows(self) -> List[WizardWorkflow]:
        """List available workflows."""
        return list(self.workflows.values())

    def start_workflow(self, workflow_id: str) -> WizardStep:
        """
        Start a workflow.

        Args:
            workflow_id: ID of workflow to start

        Returns:
            First step of the workflow
        """
        if workflow_id not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        self.current_workflow = self.workflows[workflow_id]
        self.session.set_workflow(workflow_id)
        self.session.transition_to(SessionState.SELECT_WORKFLOW)

        # Go to first step
        self.current_step = self.current_workflow.steps[self.current_workflow.start_step]
        return self.current_step

    def get_current_step(self) -> Optional[WizardStep]:
        """Get the current step."""
        return self.current_step

    def submit_input(self, value: Any) -> Optional[WizardStep]:
        """
        Submit input for the current step.

        Args:
            value: User's input

        Returns:
            Next step, or None if complete
        """
        if not self.current_step:
            return None

        step = self.current_step

        # Store input if this is an input step
        if step.step_type == WizardStepType.INPUT and step.input_key:
            self.session.add_input(step.input_key, value)

        # Handle choice steps
        if step.step_type == WizardStepType.CHOICE:
            for choice in step.choices:
                if choice.key == value:
                    self.session.add_input(f"{step.id}_choice", value)
                    if choice.next_step:
                        return self._go_to_step(choice.next_step)
                    break

        # Go to next step
        if step.next_step:
            return self._go_to_step(step.next_step)

        # Complete
        self.session.transition_to(SessionState.COMPLETE)
        return None

    def go_back(self) -> Optional[WizardStep]:
        """
        Go to the previous step.

        Returns:
            Previous step, or None if at start
        """
        if not self.current_step or not self.current_step.previous_step:
            return None

        return self._go_to_step(self.current_step.previous_step)

    def _go_to_step(self, step_id: str) -> WizardStep:
        """Navigate to a specific step."""
        if not self.current_workflow:
            raise ValueError("No workflow active")

        if step_id not in self.current_workflow.steps:
            raise ValueError(f"Unknown step: {step_id}")

        self.current_step = self.current_workflow.steps[step_id]

        # Update session state based on step type
        if self.current_step.step_type == WizardStepType.INPUT:
            self.session.transition_to(SessionState.COLLECT_INPUTS)
        elif self.current_step.step_type == WizardStepType.CONFIRM:
            self.session.transition_to(SessionState.CONFIRM)
        elif self.current_step.step_type == WizardStepType.EXECUTE:
            self.session.transition_to(SessionState.EXECUTE)

        return self.current_step

    def cancel(self) -> None:
        """Cancel the current workflow."""
        self.session.transition_to(SessionState.CANCELLED)
        self.current_workflow = None
        self.current_step = None

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress through the workflow."""
        if not self.current_workflow:
            return {"active": False}

        total_steps = len(self.current_workflow.steps)
        completed = len(self.session.completed_steps)

        return {
            "active": True,
            "workflow_id": self.current_workflow.id,
            "workflow_title": self.current_workflow.title,
            "current_step": self.current_step.id if self.current_step else None,
            "current_step_title": self.current_step.title if self.current_step else None,
            "total_steps": total_steps,
            "completed_steps": completed,
            "progress_percent": int((completed / total_steps) * 100) if total_steps > 0 else 0,
            "inputs": dict(self.session.inputs),
        }

    def format_step(self, step: WizardStep) -> str:
        """Format a step for display."""
        lines = [
            f"## {step.title}",
            "",
            step.message,
        ]

        if step.step_type == WizardStepType.INPUT:
            default = f" [{step.input_default}]" if step.input_default else ""
            lines.extend([
                "",
                f"{step.input_prompt or 'Enter value'}{default}: ",
            ])

        elif step.step_type == WizardStepType.CHOICE:
            lines.append("")
            for i, choice in enumerate(step.choices, 1):
                lines.append(f"  {i}. {choice.label}")
                if choice.description:
                    lines.append(f"     {choice.description}")

        elif step.step_type == WizardStepType.CONFIRM:
            lines.extend([
                "",
                "Proceed? [y/n]: ",
            ])

        if step.help_topic:
            lines.extend([
                "",
                f"(For help, type: processos help {step.help_topic})",
            ])

        return "\n".join(lines)
