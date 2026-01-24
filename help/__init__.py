"""
ProcessOS Help Module

Context-aware help system with interactive wizard support.
Provides help topics, error explanations, and guided workflows.
"""

from .explainer import (
    HelpExplainer,
    HelpTopic,
)
from .session import (
    InteractiveSession,
    SessionState,
)
from .wizard import (
    InteractiveWizard,
    WizardChoice,
    WizardStep,
    WizardStepType,
    WizardWorkflow,
)
from .topics import (
    register_core_topics,
    register_error_topics,
    register_file_topics,
)

__all__ = [
    # Explainer
    "HelpExplainer",
    "HelpTopic",
    # Session
    "InteractiveSession",
    "SessionState",
    # Wizard
    "InteractiveWizard",
    "WizardChoice",
    "WizardStep",
    "WizardStepType",
    "WizardWorkflow",
    # Topics
    "register_core_topics",
    "register_error_topics",
    "register_file_topics",
]
