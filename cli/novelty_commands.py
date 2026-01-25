"""
CLI commands for novelty task detection and analysis.

Commands:
- processos novelty analyze <description> - Analyze if a task is novel
- processos novelty explain <task_id> - Explain novelty determination
- processos novelty strategy <description> - Generate problem-solving strategy
"""

from typing import Optional, Dict, Any
from argparse import ArgumentParser
import sys
import json
from pathlib import Path
from datetime import datetime

from process_os.novelty.detector import NoveltyDetector, ScoringBreakdown
from process_os.novelty.scorer import SemanticScorer, StructuralScorer
from process_os.novelty.strategy_generator import StrategyGenerator


class NoveltyFormatter:
    """Formats novelty detection results for terminal display."""

    @staticmethod
    def format_novelty_analysis(
        task_description: str,
        breakdown: ScoringBreakdown,
    ) -> str:
        """
        Format novelty analysis for terminal display.

        Args:
            task_description: Task description
            breakdown: ScoringBreakdown with analysis results

        Returns:
            Formatted output string
        """
        lines = [
            "=" * 80,
            "NOVELTY DETECTION ANALYSIS",
            "=" * 80,
            "",
            f"Task: {task_description}",
            "",
            "Similarity Scores:",
            "-" * 40,
            f"  Semantic Similarity:    {breakdown.semantic_score:.1%}",
            f"  Structural Similarity:  {breakdown.structural_score:.1%}",
            f"  Hybrid Score:           {breakdown.hybrid_score:.1%}",
            "",
            f"Novelty Determination: {'NOVEL' if breakdown.is_novel else 'NOT NOVEL'}",
            f"Threshold: <0.85 for novel",
            "",
            "Explanation:",
            "-" * 40,
            breakdown.explanation,
        ]

        if breakdown.similar_patterns:
            lines.extend([
                "",
                "Similar Patterns Found:",
                "-" * 40,
            ])
            for i, pattern in enumerate(breakdown.similar_patterns, 1):
                lines.append(
                    f"  {i}. {pattern['pattern_name']} "
                    f"(match: {pattern['combined_score']:.1%})"
                )

        lines.extend([
            "",
            "=" * 80,
        ])

        return "\n".join(lines)

    @staticmethod
    def format_strategy(
        strategy_text: str,
    ) -> str:
        """
        Format problem-solving strategy for display.

        Args:
            strategy_text: Strategy formatted text

        Returns:
            Terminal-friendly output
        """
        return strategy_text

    @staticmethod
    def format_json_output(data: Dict[str, Any]) -> str:
        """
        Format output as JSON.

        Args:
            data: Data to format

        Returns:
            JSON string
        """
        return json.dumps(data, indent=2, default=str)


def novelty_analyze_command(args) -> int:
    """
    Analyze if a task is novel.

    Command: processos novelty analyze <description>

    Args:
        args: Command arguments with description

    Returns:
        Exit code
    """
    task_description = args.description
    task_structure = args.structure or ""

    # Initialize detector with known patterns
    detector = NoveltyDetector()

    # Add some default patterns
    detector.add_pattern(
        "REST API",
        "REST API with CRUD operations",
        "class Controller with create read update delete methods",
    )
    detector.add_pattern(
        "Database Model",
        "Database model with ORM",
        "class Model with fields and relationships",
    )
    detector.add_pattern(
        "Authentication",
        "User authentication with JWT or sessions",
        "class Auth with login logout refresh methods",
    )
    detector.add_pattern(
        "Service Layer",
        "Business logic service layer",
        "class Service with business methods",
    )

    # Perform analysis
    breakdown = detector.detect_novelty(task_description, task_structure)

    # Format output
    if args.json:
        output_data = {
            "task": task_description,
            "is_novel": breakdown.is_novel,
            "scores": {
                "semantic": breakdown.semantic_score,
                "structural": breakdown.structural_score,
                "hybrid": breakdown.hybrid_score,
            },
            "similar_patterns": breakdown.similar_patterns,
            "explanation": breakdown.explanation,
        }
        print(NoveltyFormatter.format_json_output(output_data))
    else:
        print(NoveltyFormatter.format_novelty_analysis(task_description, breakdown))

    # Save scoring breakdown if requested
    if args.output:
        task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        output_file = detector.save_scoring_breakdown(task_id, breakdown, args.output)
        print(f"\n✓ Analysis saved to: {output_file}")

    return 0 if breakdown.is_novel is not None else 1


def novelty_strategy_command(args) -> int:
    """
    Generate problem-solving strategy for novel task.

    Command: processos novelty strategy <description>

    Args:
        args: Command arguments with description

    Returns:
        Exit code
    """
    task_description = args.description
    task_structure = args.structure or ""

    # Generate strategy
    generator = StrategyGenerator()
    strategy = generator.generate_strategy(
        task_id=f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        task_description=task_description,
        task_structure=task_structure,
    )

    # Format output
    if args.json:
        output_data = {
            "task_id": strategy.task_id,
            "task_description": strategy.task_description,
            "strategy_name": strategy.strategy_name,
            "created_at": strategy.created_at,
            "estimated_hours": strategy.estimated_implementation_hours,
            "estimated_lines": strategy.estimated_lines_of_code,
            "risk_level": strategy.risk_level,
            "components": [
                {
                    "type": c.component_type,
                    "description": c.description,
                    "content_length": len(c.content),
                }
                for c in strategy.components
            ],
        }
        print(NoveltyFormatter.format_json_output(output_data))
    else:
        strategy_text = generator.format_strategy(strategy)
        print(NoveltyFormatter.format_strategy(strategy_text))

    return 0


def novelty_validate_command(args) -> int:
    """
    Validate novelty detection on test dataset.

    Command: processos novelty validate

    Args:
        args: Command arguments

    Returns:
        Exit code
    """
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML is required for validation. Install with: pip install pyyaml")
        return 1

    # Load test dataset
    dataset_path = Path(__file__).parent.parent / "tests" / "fixtures" / "novelty_test_dataset.yaml"

    if not dataset_path.exists():
        print(f"ERROR: Test dataset not found at {dataset_path}")
        return 1

    try:
        with open(dataset_path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Failed to load dataset: {e}")
        return 1

    # Initialize detector
    detector = NoveltyDetector()
    detector.add_pattern("CRUD", "CRUD operations", "create read update delete")
    detector.add_pattern("Authentication", "Authentication system", "login logout")
    detector.add_pattern("REST API", "REST API", "GET POST PUT DELETE")

    # Test on dataset
    tasks = data.get("tasks", [])
    correct = 0
    total = 0

    results = []

    for task in tasks:
        total += 1
        breakdown = detector.detect_novelty(
            task["description"],
            task.get("structure", ""),
        )

        expected_novel = task.get("is_novel", False)
        predicted_novel = breakdown.is_novel

        is_correct = expected_novel == predicted_novel
        if is_correct:
            correct += 1

        results.append({
            "task_id": task["id"],
            "expected": expected_novel,
            "predicted": predicted_novel,
            "correct": is_correct,
            "score": breakdown.hybrid_score,
        })

    # Display results
    accuracy = correct / total if total > 0 else 0

    print("=" * 80)
    print("NOVELTY DETECTION VALIDATION RESULTS")
    print("=" * 80)
    print(f"Total Tests: {total}")
    print(f"Correct: {correct}")
    print(f"Incorrect: {total - correct}")
    print(f"Accuracy: {accuracy:.1%}")
    print(f"Target: 95%+")
    print(f"Status: {'✓ PASS' if accuracy >= 0.95 else '✗ FAIL'}")
    print("")

    if args.verbose:
        print("Detailed Results:")
        print("-" * 80)
        for result in results:
            status = "✓" if result["correct"] else "✗"
            print(
                f"{status} {result['task_id']}: "
                f"expected={result['expected']}, "
                f"predicted={result['predicted']}, "
                f"score={result['score']:.2f}"
            )

    return 0 if accuracy >= 0.95 else 1


def create_novelty_parser(subparsers):
    """
    Create novelty subcommand parser.

    Args:
        subparsers: Parent argument subparsers

    Returns:
        Novelty parser
    """
    novelty_parser = subparsers.add_parser(
        "novelty",
        help="Detect novel tasks and generate problem-solving strategies",
    )

    novelty_subparsers = novelty_parser.add_subparsers(
        dest="novelty_command",
        help="Novelty command",
    )

    # analyze subcommand
    analyze_parser = novelty_subparsers.add_parser(
        "analyze",
        help="Analyze if task is novel",
    )
    analyze_parser.add_argument(
        "description",
        help="Task description to analyze",
    )
    analyze_parser.add_argument(
        "--structure",
        "-s",
        default="",
        help="Code structure representation",
    )
    analyze_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        help="Save analysis to directory",
    )
    analyze_parser.set_defaults(func=novelty_analyze_command)

    # strategy subcommand
    strategy_parser = novelty_subparsers.add_parser(
        "strategy",
        help="Generate problem-solving strategy for novel task",
    )
    strategy_parser.add_argument(
        "description",
        help="Task description",
    )
    strategy_parser.add_argument(
        "--structure",
        "-s",
        default="",
        help="Code structure representation",
    )
    strategy_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    strategy_parser.set_defaults(func=novelty_strategy_command)

    # validate subcommand
    validate_parser = novelty_subparsers.add_parser(
        "validate",
        help="Validate novelty detection on test dataset",
    )
    validate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed results",
    )
    validate_parser.set_defaults(func=novelty_validate_command)

    return novelty_parser


# Export for integration with main CLI
__all__ = [
    "novelty_analyze_command",
    "novelty_strategy_command",
    "novelty_validate_command",
    "create_novelty_parser",
    "NoveltyFormatter",
]
