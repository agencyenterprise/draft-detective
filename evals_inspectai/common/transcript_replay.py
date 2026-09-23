"""Replay backend agent conversations into the Inspect transcript.

E2E evals run the workflow in the API server, so Inspect never sees its model
calls. This rebuilds them from the conversations the workflow persists: each
assistant turn becomes a ModelEvent whose input is everything the model had
seen at that point, system prompt included. A run with a single conversation
has its calls directly in the transcript; a fan-out run groups each
conversation under its own agent span, all alike.
"""

from typing import Any, List, Optional

from inspect_ai.event import ModelEvent
from inspect_ai.log import transcript
from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessage,
    ChatMessageAssistant,
    GenerateConfig,
    ModelOutput,
    ModelUsage,
)
from inspect_ai.util import span
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.utils import convert_to_messages
from pydantic import BaseModel, ConfigDict

from evals_inspectai.common.converters import messages_from_langchain

# Inspect's span type for agent runs; the viewer groups and labels these as agents.
AGENT_SPAN_TYPE = "agent"


class Conversation(BaseModel):
    """One backend agent run: its label, optional metadata, and its messages."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str
    metadata: Optional[dict] = None
    messages: List[BaseMessage]


def messages_from_state(raw_messages: List[Any]) -> List[BaseMessage]:
    """Rebuild persisted LangChain messages, keeping each reply's token usage.

    `convert_to_messages` drops `usage_metadata` when rebuilding an AI message
    from its dict, so it is restored from the dict afterwards.
    """
    messages = convert_to_messages(raw_messages)
    for raw, message in zip(raw_messages, messages):
        if isinstance(message, AIMessage) and isinstance(raw, dict) and raw.get("usage_metadata"):
            message.usage_metadata = raw["usage_metadata"]
    return messages


async def replay_conversation(
    conversation: Conversation, *, as_sub_agent: bool
) -> List[ChatMessage]:
    """Record the conversation's model calls as events and return its messages.

    The main conversation's calls go straight into the transcript; a sub-agent's
    are grouped under an agent span named after it, the way Inspect nests
    sub-agents it runs itself. The returned messages are the conversation
    converted for the Messages tab, with `metadata` attached to the first one.
    """
    converted = messages_from_langchain(conversation.messages)
    if as_sub_agent:
        async with span(conversation.label, type=AGENT_SPAN_TYPE):
            _record_model_calls(conversation.messages, converted)
    else:
        _record_model_calls(conversation.messages, converted)

    if converted and conversation.metadata:
        converted[0].metadata = {**(converted[0].metadata or {}), **conversation.metadata}
    return converted


async def replay_conversations(conversations: List[Conversation]) -> List[ChatMessage]:
    """Replay every conversation into the transcript.

    A single conversation is the whole run: its calls go straight into the
    transcript and its messages are returned for the Messages tab. With several
    (a fan-out), none is more "main" than the others, so each is grouped under
    its own agent span alike and nothing is returned for the Messages tab.
    """
    if len(conversations) == 1:
        return await replay_conversation(conversations[0], as_sub_agent=False)
    for conversation in conversations:
        await replay_conversation(conversation, as_sub_agent=True)
    return []


def _record_model_calls(originals: List[BaseMessage], converted: List[ChatMessage]) -> None:
    for index, (original, message) in enumerate(zip(originals, converted)):
        if isinstance(message, ChatMessageAssistant):
            # Inspect has no public API for recording a model call made
            # outside it; `_event` is what its own span and logger use.
            transcript()._event(_model_event(converted[:index], message, original))


def _model_event(
    history: List[ChatMessage], reply: ChatMessageAssistant, original: BaseMessage
) -> ModelEvent:
    model = _model_name(original)
    return ModelEvent(
        model=model,
        input=history,
        tools=[],
        tool_choice="auto",
        config=GenerateConfig(),
        output=ModelOutput(
            model=model,
            choices=[
                ChatCompletionChoice(
                    message=reply,
                    stop_reason="tool_calls" if reply.tool_calls else "stop",
                )
            ],
            usage=_usage(original),
        ),
    )


def _model_name(message: BaseMessage) -> str:
    metadata: dict[str, Any] = getattr(message, "response_metadata", None) or {}
    return str(metadata.get("model_name") or metadata.get("model") or "unknown")


def _usage(message: BaseMessage) -> Optional[ModelUsage]:
    usage = message.usage_metadata if isinstance(message, AIMessage) else None
    if not usage:
        return None
    input_details: dict[str, Any] = dict(usage.get("input_token_details") or {})
    output_details: dict[str, Any] = dict(usage.get("output_token_details") or {})
    return ModelUsage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        input_tokens_cache_read=input_details.get("cache_read"),
        # Anthropic reports prompt-cache writes separately from reads.
        input_tokens_cache_write=input_details.get("cache_creation"),
        reasoning_tokens=output_details.get("reasoning"),
    )
