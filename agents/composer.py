"""
ProcessOS Squad Composer Module

Composes agents into squads for executing integration workflows.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .types import (
    CoordinationRule,
    CoordinationType,
    Squad,
    SquadMember,
)

if TYPE_CHECKING:
    from ..playbook import DynamicPlaybook, PlaybookStep
    from .factory import AgentFactory
    from .registry import AgentRegistry


class SquadComposer:
    """
    Composes agents into squads based on workflow requirements.

    Features:
    - Select agents based on step capabilities
    - Generate coordination rules from dependencies
    - Support agent reuse across steps
    - Dynamic squad adjustment
    """

    def __init__(
        self,
        factory: Optional["AgentFactory"] = None,
        registry: Optional["AgentRegistry"] = None,
    ):
        """
        Initialize the composer.

        Args:
            factory: Agent factory for creating/finding agents
            registry: Agent registry for looking up existing agents
        """
        self.factory = factory
        self.registry = registry

    def compose(
        self,
        playbook: "DynamicPlaybook",
        context: Optional[Dict[str, Any]] = None,
    ) -> Squad:
        """
        Compose a squad for executing a playbook.

        Args:
            playbook: Playbook to execute
            context: Optional additional context

        Returns:
            Squad configured for the playbook
        """
        squad_id = str(uuid.uuid4())[:8]

        squad = Squad(
            id=squad_id,
            name=f"Squad for {playbook.name}" if hasattr(playbook, "name") else f"Squad {squad_id}",
            playbook_id=playbook.id,
        )

        # Assign agents to steps
        step_assignments = self._assign_agents_to_steps(playbook.steps)

        # Add members to squad
        for step_id, agent_info in step_assignments.items():
            member = SquadMember(
                agent_id=agent_info["agent_id"],
                role=agent_info["role"],
                assigned_steps=[step_id],
                priority=agent_info.get("priority", 1),
            )
            squad.add_member(member)

        # Consolidate members (merge if same agent assigned to multiple steps)
        squad = self._consolidate_members(squad)

        # Generate coordination rules
        coordination_rules = self._generate_coordination_rules(playbook.steps, squad)
        squad.coordination_rules = coordination_rules

        return squad

    def _assign_agents_to_steps(
        self,
        steps: List["PlaybookStep"],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Assign agents to playbook steps.

        Args:
            steps: List of playbook steps

        Returns:
            Dict mapping step_id to agent assignment info
        """
        assignments = {}

        for i, step in enumerate(steps):
            step_type = step.step_type.value if hasattr(step.step_type, "value") else str(step.step_type)

            # Infer required capabilities
            if self.factory:
                capabilities = self.factory.infer_capabilities(step_type)
            else:
                capabilities = [step_type]

            # Try to find matching agent
            agent_id = None
            if self.factory:
                agent_id = self.factory.find_matching_agent(capabilities)

            # Create new agent if no match
            if not agent_id:
                if self.factory:
                    agent = self.factory.create_agent(
                        capabilities=capabilities,
                        name=f"{step_type.replace('_', ' ').title()} Agent",
                    )
                    agent_id = agent.id
                else:
                    agent_id = f"agent_{step_type}_{uuid.uuid4().hex[:4]}"

            # Determine role from step type
            role = self._determine_role(step_type)

            assignments[step.id] = {
                "agent_id": agent_id,
                "role": role,
                "priority": i + 1,  # Priority based on step order
                "capabilities": capabilities,
            }

        return assignments

    def _determine_role(self, step_type: str) -> str:
        """Determine agent role from step type."""
        role_mapping = {
            "discovery": "analyzer",
            "intent_analysis": "analyzer",
            "requirements_gather": "collector",
            "material_collection": "collector",
            "schema_mapping": "mapper",
            "user_confirmation": "coordinator",
            "code_generation": "generator",
            "code_review": "reviewer",
            "code_application": "applier",
        }
        return role_mapping.get(step_type.lower(), "worker")

    def _consolidate_members(self, squad: Squad) -> Squad:
        """
        Consolidate squad members to avoid duplicates.

        Args:
            squad: Squad to consolidate

        Returns:
            Consolidated squad
        """
        # Group by agent_id
        agent_steps: Dict[str, List[str]] = {}
        agent_info: Dict[str, Dict[str, Any]] = {}

        for member in squad.agents:
            if member.agent_id not in agent_steps:
                agent_steps[member.agent_id] = []
                agent_info[member.agent_id] = {
                    "role": member.role,
                    "priority": member.priority,
                }
            agent_steps[member.agent_id].extend(member.assigned_steps)
            # Keep lowest priority (highest precedence)
            if member.priority < agent_info[member.agent_id]["priority"]:
                agent_info[member.agent_id]["priority"] = member.priority

        # Rebuild members list
        squad.agents = []
        for agent_id, steps in agent_steps.items():
            squad.add_member(SquadMember(
                agent_id=agent_id,
                role=agent_info[agent_id]["role"],
                assigned_steps=list(set(steps)),  # Remove duplicates
                priority=agent_info[agent_id]["priority"],
            ))

        return squad

    def _generate_coordination_rules(
        self,
        steps: List["PlaybookStep"],
        squad: Squad,
    ) -> List[CoordinationRule]:
        """
        Generate coordination rules from step dependencies.

        Args:
            steps: Playbook steps
            squad: Squad with agent assignments

        Returns:
            List of coordination rules
        """
        rules = []

        for step in steps:
            depends_on = getattr(step, "depends_on", None)
            # Handle Mock objects and non-iterable values
            if not depends_on or not hasattr(depends_on, '__iter__') or isinstance(depends_on, str):
                continue

            # Get agent for this step
            step_agents = squad.get_agents_for_step(step.id)
            if not step_agents:
                continue

            target_agent = step_agents[0].agent_id

            # Create handoff rules from dependencies
            try:
                dep_list = list(depends_on)
            except (TypeError, ValueError):
                continue

            for dep_step_id in dep_list:
                dep_agents = squad.get_agents_for_step(dep_step_id)
                if not dep_agents:
                    continue

                source_agent = dep_agents[0].agent_id

                # Only create rule if different agents
                if source_agent != target_agent:
                    rule = CoordinationRule(
                        rule_type=CoordinationType.HANDOFF,
                        source_agent=source_agent,
                        target_agent=target_agent,
                        trigger=f"step_{dep_step_id}_complete",
                        action="pass_context",
                    )
                    rules.append(rule)

        return rules

    def adjust_squad(
        self,
        squad: Squad,
        adjustments: Dict[str, Any],
    ) -> Squad:
        """
        Dynamically adjust a squad during execution.

        Args:
            squad: Squad to adjust
            adjustments: Dict with adjustment instructions

        Returns:
            Adjusted squad
        """
        # Handle agent replacement
        if "replace_agent" in adjustments:
            old_id = adjustments["replace_agent"]["old"]
            new_id = adjustments["replace_agent"]["new"]

            for member in squad.agents:
                if member.agent_id == old_id:
                    member.agent_id = new_id

        # Handle adding new agent
        if "add_agent" in adjustments:
            add_info = adjustments["add_agent"]
            squad.add_member(SquadMember(
                agent_id=add_info["agent_id"],
                role=add_info.get("role", "worker"),
                assigned_steps=add_info.get("steps", []),
                priority=add_info.get("priority", len(squad.agents) + 1),
            ))

        # Handle removing agent
        if "remove_agent" in adjustments:
            squad.remove_member(adjustments["remove_agent"])

        # Handle step reassignment
        if "reassign_step" in adjustments:
            reassign = adjustments["reassign_step"]
            step_id = reassign["step_id"]
            new_agent_id = reassign["agent_id"]

            # Remove step from current agent
            for member in squad.agents:
                if step_id in member.assigned_steps:
                    member.assigned_steps.remove(step_id)

            # Add to new agent (create member if needed)
            found = False
            for member in squad.agents:
                if member.agent_id == new_agent_id:
                    member.assigned_steps.append(step_id)
                    found = True
                    break

            if not found:
                squad.add_member(SquadMember(
                    agent_id=new_agent_id,
                    role="worker",
                    assigned_steps=[step_id],
                ))

        return squad

    def get_squad_summary(self, squad: Squad) -> Dict[str, Any]:
        """
        Get a summary of squad composition.

        Args:
            squad: Squad to summarize

        Returns:
            Summary dict
        """
        return {
            "squad_id": squad.id,
            "name": squad.name,
            "status": squad.status.value,
            "agent_count": len(squad.agents),
            "agents": [
                {
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "step_count": len(m.assigned_steps),
                    "steps": m.assigned_steps,
                }
                for m in sorted(squad.agents, key=lambda x: x.priority)
            ],
            "coordination_rule_count": len(squad.coordination_rules),
            "completed_steps": len(squad.completed_steps),
            "current_step": squad.current_step,
        }
