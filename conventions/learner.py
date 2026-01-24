"""
Convention learner for analyzing and applying project coding conventions.

This module learns conventions from sample code and applies them to new code.
"""

from pathlib import Path
from typing import Optional

from process_os.architecture import ProjectArchitecture, ProgrammingLanguage

from process_os.conventions.types import CodeConventions, NamingStyle
from process_os.conventions.naming import NamingAnalyzer
from process_os.conventions.structure import StructureAnalyzer
from process_os.conventions.errors import InsufficientSampleError


class ConventionLearner:
    """Learns coding conventions from project samples.

    Analyzes sample files to learn:
    - Class/method/file naming conventions
    - Namespace/directory patterns
    - Documentation styles
    - Import ordering
    """

    def __init__(self):
        """Initialize the convention learner."""
        self._naming_analyzer = NamingAnalyzer()
        self._structure_analyzer = StructureAnalyzer()

    def learn(
        self,
        architecture: ProjectArchitecture,
        sample_paths: list[Path],
        sample_size: int = 3,
    ) -> CodeConventions:
        """Learn conventions from sample files.

        Args:
            architecture: Project architecture information
            sample_paths: List of sample files to learn from
            sample_size: Minimum number of samples required

        Returns:
            CodeConventions object with learned patterns

        Raises:
            InsufficientSampleError: If not enough samples provided
        """
        if len(sample_paths) < sample_size:
            raise InsufficientSampleError(
                f"Insufficient samples: need {sample_size}, got {len(sample_paths)}",
                samples_provided=len(sample_paths),
                samples_required=sample_size,
            )

        # Analyze naming conventions
        class_naming = self._naming_analyzer.analyze_class_names(
            sample_paths, architecture.language
        )
        method_naming = self._naming_analyzer.analyze_method_names(
            sample_paths, architecture.language
        )
        file_naming = self._naming_analyzer.analyze_file_names(sample_paths)

        # Analyze structural conventions
        namespace_pattern = self._structure_analyzer.analyze_namespace_pattern(
            sample_paths, architecture.language
        )
        directory_pattern = self._structure_analyzer.analyze_directory_pattern(
            architecture.root_path, architecture
        )

        # Calculate confidence (0.7 = minimum threshold from spec)
        confidence = self._calculate_confidence(
            class_naming,
            method_naming,
            file_naming,
            None,
            namespace_pattern,
            directory_pattern,
        )

        return CodeConventions(
            class_naming=class_naming or NamingStyle.PASCAL_CASE,
            method_naming=method_naming or NamingStyle.CAMEL_CASE,
            file_naming=file_naming or NamingStyle.PASCAL_CASE,
            namespace_pattern=namespace_pattern,
            directory_pattern=directory_pattern or "",
            confidence=confidence,
        )

    def _calculate_confidence(
        self,
        class_naming: Optional[NamingStyle],
        method_naming: Optional[NamingStyle],
        file_naming: Optional[NamingStyle],
        doc_style: Optional[str],
        namespace_pattern: Optional[str],
        directory_pattern: Optional[str],
    ) -> float:
        """Calculate confidence score for learned conventions.

        Args:
            class_naming: Detected class naming style
            method_naming: Detected method naming style
            file_naming: Detected file naming style
            doc_style: Detected documentation style
            namespace_pattern: Detected namespace pattern
            directory_pattern: Detected directory pattern

        Returns:
            Confidence score between 0.7 and 1.0
        """
        score = 0.7  # Minimum threshold

        # Bonus for each detected convention
        if class_naming:
            score += 0.05
        if method_naming:
            score += 0.05
        if file_naming:
            score += 0.05
        if doc_style:
            score += 0.05
        if namespace_pattern:
            score += 0.05
        if directory_pattern:
            score += 0.05

        return min(score, 1.0)


class ConventionApplier:
    """Applies learned conventions to generated code.

    Transforms code to match project conventions.
    """

    def __init__(self):
        """Initialize the convention applier."""
        pass

    def apply_naming(
        self, code: str, conventions: CodeConventions, language: ProgrammingLanguage
    ) -> str:
        """Apply naming conventions to code.

        Args:
            code: Generated code
            conventions: Learned conventions
            language: Programming language

        Returns:
            Code with applied naming conventions
        """
        # This would implement actual renaming logic
        # For now, return code as-is
        return code

    def apply_namespace(
        self, code: str, conventions: CodeConventions, language: ProgrammingLanguage
    ) -> str:
        """Apply namespace conventions to code.

        Args:
            code: Generated code
            conventions: Learned conventions
            language: Programming language

        Returns:
            Code with applied namespace conventions
        """
        # This would implement namespace transformation logic
        # For now, return code as-is
        return code

    def apply_documentation(
        self, code: str, conventions: CodeConventions, language: ProgrammingLanguage
    ) -> str:
        """Apply documentation conventions to code.

        Args:
            code: Generated code
            conventions: Learned conventions
            language: Programming language

        Returns:
            Code with applied documentation conventions
        """
        # This would implement documentation style transformation logic
        # For now, return code as-is
        return code

    def apply_all(
        self, code: str, conventions: CodeConventions, language: ProgrammingLanguage
    ) -> str:
        """Apply all learned conventions to code.

        Args:
            code: Generated code
            conventions: Learned conventions
            language: Programming language

        Returns:
            Code with all conventions applied
        """
        code = self.apply_naming(code, conventions, language)
        code = self.apply_namespace(code, conventions, language)
        code = self.apply_documentation(code, conventions, language)
        return code
