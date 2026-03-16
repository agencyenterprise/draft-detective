from collections.abc import Callable
from typing import Any

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ModelOutput
from langgraph.graph.state import RunnableConfig

from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.internal.common.config import (
    apply_inspectai_config_to_agent,
    get_runnable_config,
)
from lib.models.agent import LangChainAgent
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from tests.conftest import create_test_context

InvokeFunc = Callable[[LangChainAgent, str, RunnableConfig], Any]


@agent
def langchain_agent(
    langchain_agent_class: type[LangChainAgent],
    invoke_func: InvokeFunc | None = None,
) -> Agent:
    async def execute(state: AgentState) -> AgentState:
        document_content = state.messages[0].text if state.messages else ""

        main_file = FileDocument(
            file_name="document.md",
            file_path="document.md",
            file_type="text/markdown",
            markdown=document_content,
            markdown_token_count=len(document_content.split()),
            file_id="eval-document",
        )
        file_artifacts_service = MockFileArtifactsService(main_file=main_file)
        context = create_test_context(file_artifacts_service=file_artifacts_service)

        lc_agent = langchain_agent_class(context)
        apply_inspectai_config_to_agent(lc_agent)

        call = invoke_func or _default_invoke
        response, lc_messages = await call(
            lc_agent, document_content, get_runnable_config()
        )

        state.output = ModelOutput(
            completion=response.model_dump_json(),
            model=lc_agent.model.get_model_name_for_inspectai(),
        )
        state.messages = messages_from_langchain(lc_messages)

        return state

    return execute


async def _default_invoke(
    agent: LangChainAgent, input: str, config: RunnableConfig
) -> Any:
    return await agent.ainvoke({}, config=config)
