"""
ProcessOS Interactive Mapping Module

Handles interactive confirmation and review of schema mappings.
"""

from typing import List, Optional, Protocol

from .types import FieldMapping, SchemaMapping


class MappingHandler(Protocol):
    """Protocol for mapping confirmation handlers."""

    def present_mapping(self, mapping: FieldMapping) -> None:
        """Present a mapping to the user."""
        ...

    def get_decision(self, mapping: FieldMapping) -> str:
        """
        Get user decision for a mapping.

        Returns:
            'approve', 'reject', or a field name for override
        """
        ...


class InteractiveMapper:
    """
    Manages interactive mapping confirmation workflow.

    Handles:
    - Auto-approval of high-confidence mappings
    - Manual review of low-confidence mappings
    - User overrides for incorrect suggestions
    - Batch confirmation
    """

    DEFAULT_HIGH_CONFIDENCE = 0.9
    DEFAULT_LOW_CONFIDENCE = 0.6

    def __init__(
        self,
        mapping: SchemaMapping,
        handler: Optional[MappingHandler] = None,
    ):
        """
        Initialize the interactive mapper.

        Args:
            mapping: SchemaMapping to review
            handler: Optional handler for user interaction
        """
        self.mapping = mapping
        self.handler = handler

    def get_high_confidence_mappings(
        self,
        threshold: float = DEFAULT_HIGH_CONFIDENCE,
    ) -> List[FieldMapping]:
        """
        Get mappings with confidence above threshold.

        Args:
            threshold: Minimum confidence threshold

        Returns:
            List of high-confidence mappings
        """
        return [
            m for m in self.mapping.field_mappings
            if m.confidence >= threshold and m.user_approved is None
        ]

    def get_low_confidence_mappings(
        self,
        threshold: float = DEFAULT_HIGH_CONFIDENCE,
    ) -> List[FieldMapping]:
        """
        Get mappings with confidence below threshold.

        Args:
            threshold: Maximum confidence threshold

        Returns:
            List of low-confidence mappings
        """
        return [
            m for m in self.mapping.field_mappings
            if m.confidence < threshold and m.user_approved is None
        ]

    def auto_approve_high_confidence(
        self,
        threshold: float = DEFAULT_HIGH_CONFIDENCE,
    ) -> int:
        """
        Auto-approve all high-confidence mappings.

        Args:
            threshold: Minimum confidence threshold

        Returns:
            Number of mappings auto-approved
        """
        count = 0
        for mapping in self.get_high_confidence_mappings(threshold):
            self.mapping.approve_mapping(mapping.id)
            count += 1
        return count

    def run_interactive(
        self,
        handler: Optional[MappingHandler] = None,
        auto_approve_threshold: float = DEFAULT_HIGH_CONFIDENCE,
    ) -> SchemaMapping:
        """
        Run interactive mapping review workflow.

        Args:
            handler: Optional handler (uses self.handler if not provided)
            auto_approve_threshold: Threshold for auto-approval

        Returns:
            Updated SchemaMapping
        """
        handler = handler or self.handler
        if not handler:
            raise ValueError("No handler provided for interactive review")

        # Auto-approve high confidence
        self.auto_approve_high_confidence(auto_approve_threshold)

        # Review remaining
        for mapping in self.mapping.pending_approvals:
            handler.present_mapping(mapping)
            decision = handler.get_decision(mapping)

            if decision == "approve":
                self.mapping.approve_mapping(mapping.id)
            elif decision == "reject":
                self.mapping.reject_mapping(mapping.id)
            else:
                # Override with different field
                self.mapping.override_mapping(mapping.id, decision)

        return self.mapping

    def format_mapping(self, mapping: FieldMapping) -> str:
        """
        Format a mapping for display.

        Args:
            mapping: FieldMapping to format

        Returns:
            Formatted string for display
        """
        lines = [
            f"External: {mapping.external_field_path} ({mapping.external_type})",
            f"       → Local: {mapping.local_model}.{mapping.local_field} ({mapping.local_type})",
            f"       Confidence: {mapping.confidence:.0%}",
        ]

        if mapping.reasoning:
            lines.append(f"       Reason: {mapping.reasoning}")

        if mapping.transformation:
            lines.append(f"       Transform: {mapping.transformation.description}")

        return "\n".join(lines)

    def format_all_mappings(self) -> str:
        """
        Format all mappings for display.

        Returns:
            Formatted string showing all mappings
        """
        sections = []

        # Approved
        approved = self.mapping.approved_mappings
        if approved:
            sections.append("=== Approved Mappings ===")
            for m in approved:
                sections.append(self.format_mapping(m))
                sections.append("")

        # Pending
        pending = self.mapping.pending_approvals
        if pending:
            sections.append("=== Pending Review ===")
            for m in pending:
                sections.append(self.format_mapping(m))
                sections.append("")

        # Rejected
        rejected = self.mapping.rejected_mappings
        if rejected:
            sections.append("=== Rejected Mappings ===")
            for m in rejected:
                sections.append(self.format_mapping(m))
                sections.append("")

        # Unmapped
        if self.mapping.unmapped_external:
            sections.append("=== Unmapped External Fields ===")
            for u in self.mapping.unmapped_external:
                sections.append(f"  {u.field_path} ({u.field_type}): {u.reason}")
            sections.append("")

        if self.mapping.unmapped_local:
            sections.append("=== Unmapped Local Fields ===")
            for u in self.mapping.unmapped_local:
                sections.append(f"  {u.field_path} ({u.field_type}): {u.reason}")
            sections.append("")

        return "\n".join(sections)

    def get_summary(self) -> dict:
        """
        Get summary statistics for the mapping.

        Returns:
            Dict with summary statistics
        """
        return {
            "total_mappings": len(self.mapping.field_mappings),
            "approved": len(self.mapping.approved_mappings),
            "rejected": len(self.mapping.rejected_mappings),
            "pending": len(self.mapping.pending_approvals),
            "unmapped_external": len(self.mapping.unmapped_external),
            "unmapped_local": len(self.mapping.unmapped_local),
            "all_decided": self.mapping.all_decided,
            "user_confirmed": self.mapping.user_confirmed,
        }


class ConsoleMappingHandler:
    """
    Console-based mapping handler for CLI usage.
    """

    def __init__(self, interactive_mapper: Optional[InteractiveMapper] = None):
        """
        Initialize the console handler.

        Args:
            interactive_mapper: Optional InteractiveMapper for formatting
        """
        self.interactive_mapper = interactive_mapper

    def present_mapping(self, mapping: FieldMapping) -> None:
        """Present mapping to console."""
        print("\n" + "=" * 60)
        if self.interactive_mapper:
            print(self.interactive_mapper.format_mapping(mapping))
        else:
            print(f"External: {mapping.external_field_path} -> {mapping.local_model}.{mapping.local_field}")
            print(f"Confidence: {mapping.confidence:.0%}")

    def get_decision(self, mapping: FieldMapping) -> str:
        """Get user decision from console."""
        print("\nOptions:")
        print("  [a] Approve this mapping")
        print("  [r] Reject this mapping")
        print("  [o] Override with different field")
        print()

        while True:
            choice = input("Your choice [a/r/o]: ").strip().lower()

            if choice == "a":
                return "approve"
            elif choice == "r":
                return "reject"
            elif choice == "o":
                new_field = input("Enter local field name: ").strip()
                if new_field:
                    return new_field
                print("Please enter a valid field name")
            else:
                print("Invalid choice. Please enter 'a', 'r', or 'o'")
