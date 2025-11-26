"""
Agent Registry System

Provides a centralized way to register, discover, and access agents dynamically.
This eliminates hardcoded agent types throughout the system.
"""

import logging
from typing import Dict, List

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AgentInfo(BaseModel):
    """Information about a registered agent"""

    function_name: str
    name: str
    description: str


class AgentRegistry:
    """
    Central registry for all agents in the system.

    Provides dynamic agent discovery and eliminates hardcoded agent types.
    """

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}

    def register(
        self,
        function_name: str,
        name: str,
        description: str,
    ) -> None:
        """
        Register an agent with the registry

        Args:
            function_name: The name of the function that is being registered.
            name: A human-readable name for the agent.
            description: Human-readable description.
        """
        if function_name in self._agents:
            logger.warning(
                f"Overriding existing agent registration for '{function_name}'"
            )

        agent_info = AgentInfo(
            function_name=function_name, name=name, description=description
        )

        self._agents[function_name] = agent_info
        logger.info(f"Registered agent: {function_name}")

    def has_agent(self, function_name: str) -> bool:
        """Check if agent type is registered"""
        return function_name in self._agents

    def get_supported_types(self) -> List[str]:
        """Get list of all registered agent types"""
        return list(self._agents.keys())

    def get_agents_info(self) -> List[AgentInfo]:
        """Get list of AgentInfo objects"""
        return [info for info in self._agents.values()]

    def validate_agents(self, function_names: List[str]) -> None:
        """Validate that all requested agent types are available"""
        if not function_names:
            raise ValueError("agent_types cannot be empty")

        unsupported = [
            function_name
            for function_name in function_names
            if not self.has_agent(function_name)
        ]
        if unsupported:
            supported_list = ", ".join(self._agents.keys())
            raise ValueError(
                f"Unsupported agents: {unsupported}. " f"Supported: {supported_list}"
            )


# Global registry instance
agent_registry = AgentRegistry()
