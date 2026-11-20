"""Keep a failed web search in the history from failing every later model call.

OpenAI's hosted web search returns a ``web_search_call`` item, normally with an
``action`` (``{"type": "search", "query": …}``). A search that fails or is cut
short can come back without one. langchain-openai stores that call with empty
``args``, and on the next request turns them back into ``"action": {}``, which
the Responses API refuses: ``Missing required parameter: 'input[N].action.type'``.
One bad search then ends the agent's turn.

An action with no ``type`` carries nothing the model needs, and the API accepts a
``web_search_call`` with no action at all. So before each model call this drops
the arguments of any web search that lack a ``type``, in both block formats:
LangChain's standard ``server_tool_call`` blocks and OpenAI's own
``web_search_call`` blocks. The history in the agent's state is left as it is;
only the request is fixed.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage


def _without_typeless_action(block: Any) -> Any:
    """The block without its search arguments, when they lack a ``type``."""

    if not isinstance(block, dict):
        return block
    if block.get("type") == "server_tool_call" and block.get("name") == "web_search":
        key = "args"
    elif block.get("type") == "web_search_call":
        key = "action"
    else:
        return block
    action = block.get(key)
    if key in block and not (isinstance(action, dict) and action.get("type")):
        return {k: v for k, v in block.items() if k != key}
    return block


def repair_web_search_history(messages: list[AnyMessage]) -> list[AnyMessage]:
    """The messages, with every typeless web-search action dropped. Copies only what changes."""

    repaired: list[AnyMessage] = []
    for message in messages:
        if isinstance(message, AIMessage) and isinstance(message.content, list):
            content = [_without_typeless_action(block) for block in message.content]
            if any(new is not old for new, old in zip(content, message.content)):
                message = message.model_copy(update={"content": content})
        repaired.append(message)
    return repaired


class WebSearchHistoryMiddleware(AgentMiddleware[Any, Any, Any]):
    """Repairs typeless web-search actions in the history before each model call."""

    def _repair(self, request: ModelRequest) -> ModelRequest:
        return request.override(messages=repair_web_search_history(request.messages))

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._repair(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._repair(request))
