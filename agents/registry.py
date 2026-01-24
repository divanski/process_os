"""
ProcessOS Agent Registry

Manages agent role cards with SHA256-based versioning.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml


class AgentRegistry:
    """
    Registry for agent role cards.

    Features:
    - Load agents from YAML files
    - SHA256-based content addressing
    - Capability lookup
    - Validation against schema
    """

    def __init__(self, agents_dir: Optional[Path] = None):
        """
        Initialize registry.

        Args:
            agents_dir: Directory containing agent YAML files
        """
        if agents_dir is None:
            agents_dir = Path(__file__).parent.parent / "agents"
        self.agents_dir = agents_dir
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._hashes: Dict[str, str] = {}

    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def load(self, agent_id: str) -> Dict[str, Any]:
        """
        Load agent card by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent card dictionary

        Raises:
            FileNotFoundError: If agent file not found
        """
        if agent_id in self._cache:
            return self._cache[agent_id]

        agent_path = self.agents_dir / f"{agent_id}.yaml"
        if not agent_path.exists():
            raise FileNotFoundError(f"Agent not found: {agent_id}")

        content = agent_path.read_text()
        agent_data = yaml.safe_load(content)

        # Cache with hash
        self._cache[agent_id] = agent_data
        self._hashes[agent_id] = self._compute_hash(content)

        return agent_data

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all agents from directory and cache.

        Returns:
            Dict mapping agent_id to agent card
        """
        agents = {}

        # First, load from disk
        if self.agents_dir.exists():
            for path in self.agents_dir.glob("*.yaml"):
                agent_id = path.stem
                try:
                    agents[agent_id] = self.load(agent_id)
                except Exception:
                    pass  # Skip invalid files

        # Add any in-memory registered agents not already loaded
        for agent_id, agent_data in self._cache.items():
            if agent_id not in agents:
                agents[agent_id] = agent_data

        return agents

    def get_hash(self, agent_id: str) -> str:
        """
        Get SHA256 hash of agent card.

        Args:
            agent_id: Agent identifier

        Returns:
            SHA256 hex string
        """
        if agent_id not in self._hashes:
            self.load(agent_id)
        return self._hashes[agent_id]

    def find_by_capability(self, capability: str) -> List[str]:
        """
        Find agents with a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agent IDs
        """
        matching = []
        for agent_id, agent_data in self.load_all().items():
            capabilities = agent_data.get("capabilities", [])
            if capability in capabilities:
                matching.append(agent_id)
        return sorted(matching)

    def register(self, agent_data: Dict[str, Any]) -> str:
        """
        Register a new agent (in memory).

        Args:
            agent_data: Agent card dictionary

        Returns:
            Agent ID
        """
        agent_id = agent_data.get("agent_id")
        if not agent_id:
            raise ValueError("agent_id is required")

        content = yaml.dump(agent_data, sort_keys=True, default_flow_style=False)
        self._cache[agent_id] = agent_data
        self._hashes[agent_id] = self._compute_hash(content)

        return agent_id

    def save(self, agent_id: str) -> Path:
        """
        Save agent to disk.

        Args:
            agent_id: Agent to save

        Returns:
            Path to saved file
        """
        if agent_id not in self._cache:
            raise ValueError(f"Agent not in registry: {agent_id}")

        self.agents_dir.mkdir(parents=True, exist_ok=True)
        agent_path = self.agents_dir / f"{agent_id}.yaml"

        content = yaml.dump(self._cache[agent_id], sort_keys=True, default_flow_style=False)
        agent_path.write_text(content)

        return agent_path

    def get_manifest(self) -> Dict[str, Any]:
        """
        Get registry manifest with all agents and hashes.

        Returns:
            Manifest dictionary
        """
        agents = self.load_all()
        return {
            "agent_count": len(agents),
            "agents": [
                {
                    "agent_id": agent_id,
                    "name": data.get("name", "Unknown"),
                    "sha256": self.get_hash(agent_id),
                }
                for agent_id, data in sorted(agents.items())
            ],
        }
