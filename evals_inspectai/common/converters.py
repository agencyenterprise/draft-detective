import json
from typing import Literal, Union

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
)
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
