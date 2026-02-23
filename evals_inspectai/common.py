import json
import logging
from contextvars import ContextVar
from typing import Literal, Union

from inspect_ai.hooks import Hooks, TaskStart, hooks
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    Content,
    ContentReasoning,
    ContentText,
    ContentToolUse,
    Model,
    ModelName,
    get_model,
)
from inspect_ai.model._generate_config import active_generate_config
from inspect_ai.model._model import active_model
from inspect_ai.tool import ToolCall as InspectToolCall
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ServerToolCall,
    ServerToolResult,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.state import RunnableConfig

from lib.config.langfuse import langfuse_handler
from lib.config.llm_models import LLMModel
from lib.models.agent import BaseAgent, LangChainAgent

logger = logging.getLogger(__name__)

_current_task_id: ContextVar[str | None] = ContextVar("_current_task_id", default=None)
_current_task_name: ContextVar[str | None] = ContextVar(
    "_current_task_name", default=None
)


@hooks(
    "langfuse_inspectai_metadata",
    "Captures InspectAI metadata information for Langfuse session tracking",
)
class _LangfuseInspectAIMetadataHook(Hooks):
    async def on_task_start(self, data: TaskStart) -> None:
        _current_task_id.set(data.spec.task_id)
        _current_task_name.set(data.spec.task)


def get_runnable_config() -> RunnableConfig:
    """Get a RunnableConfig for InspectAI evaluations."""

    task_id = _current_task_id.get()
    task_name = _current_task_name.get()

    run_name = "inspectai_eval"
    if task_name:
        run_name = f"inspectai_eval__{task_name}"

    metadata: dict[str, str] = {}
    if task_id:
        metadata["langfuse_session_id"] = task_id

    return RunnableConfig(
        run_name=run_name,
        callbacks=[langfuse_handler],
        metadata=metadata,
    )


def apply_inspectai_config_to_agent(agent: LangChainAgent) -> None:
    """
    Override a LangChainAgent's parameters with values from the current Inspect AI
    runtime (CLI flags like --model, --temperature, --reasoning-effort, etc.).

    Only non-None config values override the agent defaults. Resets the cached
    LLM so the next call picks up the new parameters.
    """

    config = active_generate_config()
    model = active_model()

    if model is not None and model.name != "none":
        inspectai_name = str(ModelName(model))
        if inspectai_name != agent.model.get_model_name_for_inspectai():
            agent.model = LLMModel.from_inspectai_name(inspectai_name)
            logger.info("Overriding model to %s", agent.model.model_name)

    if config.temperature is not None:
        agent.temperature = config.temperature
        logger.info("Overriding temperature to %s", config.temperature)

    if config.reasoning_effort is not None or config.reasoning_summary is not None:
        reasoning = dict(agent.reasoning) if agent.reasoning else {}
        if config.reasoning_effort is not None:
            reasoning["effort"] = config.reasoning_effort
            logger.info("Overriding reasoning effort to %s", config.reasoning_effort)
        if config.reasoning_summary is not None:
            reasoning["summary"] = config.reasoning_summary
            logger.info("Overriding reasoning summary to %s", config.reasoning_summary)
        agent.reasoning = reasoning  # type: ignore[assignment]

    agent._llm = None


def get_model_or_agent_default(agent_class: type[BaseAgent]) -> Model:
    """
    Get the InspectAI Model current in use (defined via task arguments) or use the default model for the agent.

    Args:
        agent_class: The agent class to get the model for, as default, in case no model is defined via task arguments

    Returns:
        The InspectAI Model
    """

    task_model = get_model()

    if not task_model or task_model.name == "none":
        return get_model(agent_class.model.get_model_name_for_inspectai())

    return task_model


def messages_from_langchain(
    messages: list[BaseMessage],
) -> list[ChatMessage]:
    """
    Convert a list of LangChain messages to a list of InspectAI messages.

    Args:
        messages: The list of LangChain messages to convert

    Returns:
        The list of InspectAI messages
    """

    return [_convert_message(msg) for msg in messages]


def _convert_message(msg: BaseMessage) -> ChatMessage:
    content = _convert_content_blocks(msg)

    if isinstance(msg, SystemMessage):
        return ChatMessageSystem(content=content)
    elif isinstance(msg, HumanMessage):
        return ChatMessageUser(content=content)
    elif isinstance(msg, AIMessage):
        tool_calls = (
            [
                InspectToolCall(
                    id=tc["id"] or "",
                    function=tc["name"],
                    arguments=tc["args"],
                )
                for tc in msg.tool_calls
            ]
            if msg.tool_calls
            else None
        )
        return ChatMessageAssistant(content=content, tool_calls=tool_calls)
    elif isinstance(msg, ToolMessage):
        return ChatMessageTool(
            content=content,
            tool_call_id=msg.tool_call_id,
            function=msg.name or None,
        )
    else:
        return ChatMessageUser(content=content)


def _convert_content_blocks(
    msg: BaseMessage,
) -> Union[str, list[Content]]:
    blocks = msg.content_blocks
    if not blocks:
        return msg.text if isinstance(msg.content, str) else ""

    results_by_call_id: dict[str, ServerToolResult] = {}
    for block in blocks:
        if block["type"] == "server_tool_result":
            results_by_call_id[block["tool_call_id"]] = block

    result: list[Content] = []
    for block in blocks:
        if block["type"] == "text":
            result.append(ContentText(text=block["text"]))
        elif block["type"] == "reasoning":
            result.append(ContentReasoning(reasoning=block.get("reasoning", "")))
        elif block["type"] == "server_tool_call":
            result.append(_convert_server_tool_call(block, results_by_call_id))
        elif block["type"] == "server_tool_result":
            continue
        else:
            text = block.get("text", json.dumps(block))
            result.append(ContentText(text=str(text)))

    return result if result else ""


_TOOL_TYPE_MAP: dict[str, Literal["web_search", "mcp_call", "code_execution"]] = {
    "web_search": "web_search",
    "code_interpreter": "code_execution",
    "code_execution": "code_execution",
    "mcp_call": "mcp_call",
}


def _convert_server_tool_call(
    server_tool_call_block: ServerToolCall,
    results_by_call_id: dict[str, ServerToolResult],
) -> ContentToolUse:
    call_id = server_tool_call_block["id"]
    name = server_tool_call_block["name"]
    args = server_tool_call_block["args"]
    tool_type = _TOOL_TYPE_MAP.get(name, "web_search")

    tool_result = results_by_call_id.get(call_id)
    output = tool_result.get("output") if tool_result else None
    result_str = json.dumps(output) if output is not None else ""
    error = (
        None
        if not tool_result or tool_result["status"] != "error"
        else result_str or "error"
    )

    return ContentToolUse(
        tool_type=tool_type,
        id=call_id,
        name=name,
        arguments=json.dumps(args) if args else "",
        result=result_str,
        error=error,
    )
