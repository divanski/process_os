"""
Code generation module for ProcessOS.

This module provides code generation capabilities for integration points:
- Service provider/container registration
- Configuration file generation
- Route/endpoint registration
- File generation with conventions applied

Public API:
- TemplateEngine: Renders integration point templates
- GeneratedCode: Collection of generated code files
- GeneratedFile: A single generated file
- Patchset: A cohesive set of files to apply together
- generate_integration_code: Generate code for an integration
- PatchsetManager: Manage patchsets for code application
"""

from process_os.codegen.template_engine import TemplateEngine
from process_os.codegen.types import (
    GeneratedCode,
    GeneratedFile,
    Patchset,
    FileType,
    FileDecision,
    ReviewStatus,
)
from process_os.codegen.errors import (
    CodegenError,
    ConventionMismatchError,
    ApplyError,
)


# Stub functions for integration_runner compatibility
def generate_integration_code(
    project_context,
    intent,
    requirements,
    mapping,
    playbook,
):
    """Generate code for an integration.
    
    Args:
        project_context: Project discovery context
        intent: Parsed user intent
        requirements: Inferred requirements
        mapping: Schema mapping
        playbook: Dynamic playbook
        
    Returns:
        GeneratedCode object
    """
    # Stub implementation for Phase 6
    return GeneratedCode(
        playbook_id=playbook.id if hasattr(playbook, 'id') else "playbook_001",
        mapping_id=mapping.id if hasattr(mapping, 'id') else "mapping_001",
    )


class PatchsetManager:
    """Manages patchsets for code application."""
    
    def __init__(self, project_path):
        """Initialize patchset manager.
        
        Args:
            project_path: Path to the project
        """
        self.project_path = project_path
    
    def create_patchset(self, generated_code, patchset_id):
        """Create a patchset from generated code.
        
        Args:
            generated_code: GeneratedCode object
            patchset_id: ID for the patchset
            
        Returns:
            Patchset object
        """
        return Patchset.from_generated_code(patchset_id, generated_code)
    
    def apply_patchset(self, patchset):
        """Apply a patchset to the project.
        
        Args:
            patchset: Patchset to apply
        """
        patchset.apply()


__all__ = [
    "TemplateEngine",
    "GeneratedCode",
    "GeneratedFile",
    "Patchset",
    "FileType",
    "FileDecision",
    "ReviewStatus",
    "CodegenError",
    "ConventionMismatchError",
    "ApplyError",
    "generate_integration_code",
    "PatchsetManager",
]
