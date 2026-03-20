"""Generic deep agent for simple single-node workflows.

Accepts system and user prompts as constructor arguments so that
manifests can configure the agent without subclassing.
"""

from typing import List, Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_4_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.types import AgentCheckResult


class SimpleDeepAgent(LangChainAgent):
    """Deep agent that runs a single validation pass using caller-supplied prompts."""

    name = "Simple Deep Agent"
    description = "Runs a deep-agent validation pass and returns structured issues"
    model = gpt_5_4_model
    temperature = 0.0
    reasoning = {"effort": "medium", "summary": "auto"}

    def __init__(
        self,
        context: ContextSchema,
        system_prompt: str,
        user_prompt: str,
        include_supporting_files: bool = False,
    ):
        super().__init__(context)
        self._system_prompt = system_prompt
        self._user_prompt = user_prompt
        self._include_supporting_files = include_supporting_files

    async def ainvoke(
        self,
        prompt_kwargs: dict,
        config: Optional[RunnableConfig] = None,
    ) -> tuple[AgentCheckResult, List[BaseMessage]]:
        deep_agent = create_deep_agent(
            model=self.llm,
            context_schema=ContextSchema,
            response_format=AutoStrategy(AgentCheckResult),
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(
                    include_supporting_files=self._include_supporting_files,
                ),
                "messages": [
                    SystemMessage(content=self._system_prompt),
                    HumanMessage(content=self._user_prompt),
                ],
            },
            config={"recursion_limit": 100, **(config or {})},
        )

        return result["structured_response"], result["messages"]
