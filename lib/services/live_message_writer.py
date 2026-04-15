"""Appends deep-agent messages to a running workflow's state.

The writer is built in the runner (`lib/workflows/runner.py`) and attached to
`ContextSchema.live_message_writer` for workflows whose manifest opts in via
`supports_live_messages`. Inside the workflow node, the agent calls
`append(message)` each time an LLM response or tool result completes, which:

1. Redacts the message (API-key scrubbing + tool-output truncation).
2. Writes a LangGraph checkpoint appending the message to `state.messages`
   via `add_messages`, so the existing GET /api/workflows/{id} polling
   endpoint sees the growing conversation on its next tick.

Single-node simple-deep-agent graphs are the only current caller, so there's
no contention with concurrent node writers on the same thread.
"""

import copy
import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

# OpenAI-style API key pattern. Defense in depth — keys should never make it
# into messages, but redact on the off-chance they do.
_API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
_REDACTED_PLACEHOLDER = "[REDACTED_API_KEY]"

# Tool outputs can be very large (full document snippets, search results).
# Cap what we append to state so checkpoints stay a reasonable size. The
# final state still reflects what the agent saw — only the persisted copy
# is truncated.
_MAX_TOOL_CONTENT_CHARS = 10_000
_TRUNCATION_MARKER = "\n…[truncated]"


def _redact_str(value: str) -> str:
    return _API_KEY_PATTERN.sub(_REDACTED_PLACEHOLDER, value)


def _redact_content(content: Any) -> Any:
    """Redact API keys anywhere in a string or nested content block list."""
    if isinstance(content, str):
        return _redact_str(content)
    if isinstance(content, list):
        return [_redact_content(item) for item in content]
    if isinstance(content, dict):
        return {k: _redact_content(v) for k, v in content.items()}
    return content


def _truncate_tool_content(content: Any) -> Any:
    """Cap ToolMessage content at `_MAX_TOOL_CONTENT_CHARS`."""
    if isinstance(content, str) and len(content) > _MAX_TOOL_CONTENT_CHARS:
        return content[:_MAX_TOOL_CONTENT_CHARS] + _TRUNCATION_MARKER
    if isinstance(content, list):
        return [_truncate_tool_content(item) for item in content]
    return content


def _redact(message: BaseMessage) -> BaseMessage:
    """Return a copy of the message with API keys scrubbed and tool outputs bounded."""
    redacted = copy.deepcopy(message)
    redacted.content = _redact_content(redacted.content)
    if isinstance(redacted, ToolMessage):
        redacted.content = _truncate_tool_content(redacted.content)
    return redacted


class LiveMessageWriter:
    """Appends messages to the running workflow's state mid-node.

    Built by `lib.workflows.runner.run_workflow` after graph compilation and
    attached to the per-run `ContextSchema`. The workflow node pulls it off
    the context and calls `append()` as each completed message arrives from
    the deep agent's event stream.
    """

    def __init__(
        self,
        app: CompiledStateGraph,
        thread_config: dict,
        node_name: str,
    ) -> None:
        self._app = app
        self._thread_config = thread_config
        self._node_name = node_name

    async def append(self, message: BaseMessage) -> None:
        """Redact, then checkpoint a single new message onto `state.messages`."""
        redacted = _redact(message)
        try:
            await self._app.aupdate_state(
                self._thread_config,
                {"messages": [redacted]},
                as_node=self._node_name,
            )
        except Exception as e:
            # Never let a streaming-persistence failure abort the workflow.
            # The final node return still includes the full messages list, so
            # the end result is unaffected — we just lose the live update for
            # this single message. Logged at warning so it's visible in logs
            # without being mistaken for a workflow-level error.
            logger.warning(
                f"LiveMessageWriter.append failed for node {self._node_name}: {e}",
                exc_info=True,
            )
