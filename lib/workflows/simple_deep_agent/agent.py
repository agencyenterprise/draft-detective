"""Generic deep agent for simple single-node workflows.

The default system prompt defines a generic document-reviewer role.
Callers supply the user prompt (specific rules/criteria) and may optionally
override the system prompt when the default is not appropriate.
"""

from typing import List, Optional

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_5_model
from lib.models.agent import LangChainAgent
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent_types import AgentCheckResult

_SYSTEM_PROMPT = """\
You are a specialist document reviewer. Your task is to review a document \
against rules or criteria provided in the user message and report any issues found.

## Document

The document is available at `/main.md`. Use your tools to read or search its \
content as needed to evaluate the rules given by the user.

## Reporting Issues

For each rule or criterion that fails, report one issue following the conventions \
defined in the issues skill (`/skills/issues/SKILL.md`). \
Do not create issues for rules that pass.\
"""


class SimpleDeepAgent(LangChainAgent):
    """Deep agent that runs a single validation pass.

    Defaults to a generic document-reviewer system prompt; pass `system_prompt`
    to override it. The user prompt contains the specific rules to check.
    """

    name = "Simple Deep Agent"
    description = "Runs a deep-agent validation pass and returns structured issues"
    model = gpt_5_5_model
    temperature = 0.0
    reasoning = {"effort": "medium", "summary": "auto"}

    def __init__(
        self,
        context: ContextSchema,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        include_supporting_files: bool = False,
    ):
        super().__init__(context)
        self._system_prompt = system_prompt or _SYSTEM_PROMPT
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
            skills=["/skills/"],
        )

        result = await deep_agent.ainvoke(
            {
                "files": await self.context.file_artifacts_service.get_deepagent_backend_files(
                    include_supporting_files=self._include_supporting_files,
                    include_skills=True,
                ),
                "messages": [
                    SystemMessage(content=self._system_prompt),
                    HumanMessage(content=self._user_prompt),
                ],
            },
            config={"recursion_limit": 100, **(config or {})},
        )

        return result["structured_response"], result["messages"]
