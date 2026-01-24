"""
ProcessOS Rules Module

Generates Claude rules packs for projects.
"""

from .generator import RulesGenerator, generate_rules

__all__ = [
    "RulesGenerator",
    "generate_rules",
]
