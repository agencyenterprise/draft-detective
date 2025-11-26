"""
Agent Registry System

Provides a centralized way to register, discover, and access agents dynamically.
This eliminates hardcoded agent types throughout the system.
"""

import logging
from typing import Dict, List

from lib.agents.citation_detector import CitationDetectorAgent
from lib.agents.citation_suggester import CitationSuggesterAgent
from lib.agents.claim_extractor import ClaimExtractorAgent
from lib.agents.claim_needs_substantiation_checker import (
    ClaimNeedsSubstantiationCheckerAgent,
)
from lib.agents.claim_verifier import ClaimVerifierAgent
from lib.agents.evidence_weighter import EvidenceWeighterAgent
from lib.agents.literature_review import LiteratureReviewAgent
from lib.agents.live_literature_review import LiveLiteratureReviewAgent
from lib.agents.methodology_comparator import MethodologyComparisonAgent
from lib.agents.methodology_extractor import MethodologyExtractorAgent
from lib.agents.reference_extractor import ReferenceExtractorAgent
from lib.agents.reference_validator import ReferenceValidatorAgent
from lib.models.agent import BaseAgent
from lib.workflows.claim_substantiation.context import ContextSchema

logger = logging.getLogger(__name__)


class AgentInfo:
    """Information about a registered agent"""

    def __init__(
        self,
        agent_type: str,
        agent: BaseAgent,
        description: str,
    ):
        self.agent_type = agent_type
        self.agent = agent
        self.description = description

    def __repr__(self):
        return f"AgentInfo(type='{self.agent_type}', agent='{self.agent.name}')"


class AgentRegistry:
    """
    Central registry for all agents in the system.

    Provides dynamic agent discovery and eliminates hardcoded agent types.
    """

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}

    def register(
        self,
        agent_type: str,
        agent: BaseAgent,
        description: str,
    ) -> None:
        """
        Register an agent with the registry

        Args:
            agent_type: String identifier for the agent (e.g., "claims", "citations")
            agent: Agent instance (LangChainAgent or DirectOpenAIAgent)
            description: Human-readable description
        """
        if agent_type in self._agents:
            logger.warning(f"Overriding existing agent registration for '{agent_type}'")

        agent_info = AgentInfo(
            agent_type=agent_type, agent=agent, description=description
        )

        self._agents[agent_type] = agent_info
        logger.info(f"Registered agent: {agent_type} -> {agent.name}")

    def get_agent(self, agent_type: str) -> BaseAgent:
        """Get an agent by type"""
        if agent_type not in self._agents:
            raise ValueError(
                f"Unknown agent type: '{agent_type}'. Available: {list(self._agents.keys())}"
            )
        return self._agents[agent_type].agent

    def has_agent(self, agent_type: str) -> bool:
        """Check if agent type is registered"""
        return agent_type in self._agents

    def get_supported_types(self) -> List[str]:
        """Get list of all registered agent types"""
        return list(self._agents.keys())

    def get_agent_descriptions(self) -> Dict[str, str]:
        """Get mapping of agent types to descriptions"""
        return {
            agent_type: info.description for agent_type, info in self._agents.items()
        }

    def validate_agents(self, agent_types: List[str]) -> None:
        """Validate that all requested agent types are available"""
        if not agent_types:
            raise ValueError("agent_types cannot be empty")

        unsupported = [
            agent_type for agent_type in agent_types if not self.has_agent(agent_type)
        ]
        if unsupported:
            supported_list = ", ".join(self._agents.keys())
            raise ValueError(
                f"Unsupported agent types: {unsupported}. "
                f"Supported: {supported_list}"
            )


# Global registry instance
agent_registry = AgentRegistry()


def initialize_default_agents():
    """Initialize the registry with default agents"""

    # context is not needed for registry initialization
    context = ContextSchema(openai_api_key="not-needed", vector_store=None)

    agent_registry.register(
        agent_type="claims",
        agent=ClaimExtractorAgent(context),
        description="Detect and extract claims from text chunks",
    )

    agent_registry.register(
        agent_type="citations",
        agent=CitationDetectorAgent(context),
        description="Detect and extract citations from text chunks",
    )

    agent_registry.register(
        agent_type="needs_substantiation",
        agent=ClaimNeedsSubstantiationCheckerAgent(context),
        description="Determine if claims need to be substantiated or not (common knowledge etc)",
    )

    agent_registry.register(
        agent_type="substantiation",
        agent=ClaimVerifierAgent(context),
        description="Substantiate claims against supporting documents",
    )

    agent_registry.register(
        agent_type="suggest_citations",
        agent=CitationSuggesterAgent(context),
        description="Review a chunk of text against RAND attribution guidelines to identify missing citations and recommend high-quality sources for proper attribution compliance",
    )

    agent_registry.register(
        agent_type="literature_review",
        agent=LiteratureReviewAgent(context),
        description="Review a document paragraph against the article bibliography and recent literature to propose citation updates",
    )

    agent_registry.register(
        agent_type="evidence_weighter",
        agent=EvidenceWeighterAgent(context),
        description="Analyze and weight evidence from multiple sources to determine overall direction and strength",
    )

    agent_registry.register(
        agent_type="live_literature_review",
        agent=LiveLiteratureReviewAgent(context),
        description="Review a document paragraph against the article bibliography and recent literature to propose citation updates",
    )

    agent_registry.register(
        agent_type="references",
        agent=ReferenceExtractorAgent(context),
        description="Extract the list of references from a document",
    )

    agent_registry.register(
        agent_type="validate_references",
        agent=ReferenceValidatorAgent(context),
        description="Validate the list of references in a document by ensuring there is online presence from a legitimate source from each one.",
    )

    agent_registry.register(
        agent_type="methodology_extractor",
        agent=MethodologyExtractorAgent(context),
        description="Extract a concise but detailed description of the methodology used in a research document to obtain its results.",
    )

    agent_registry.register(
        agent_type="methodology_comparator",
        agent=MethodologyComparisonAgent(context),
        description="Compare an extracted paper methodology to typical methods used in the broader field, using web search to find field methods context.",
    )

    logger.info("Initialized default agent registry")


initialize_default_agents()
