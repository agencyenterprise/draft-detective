"""The agent behind the Word add-in's chat.

A fourth consumer of ``lib/agents/deep_agent_setup.py``. It streams like the /chat
agent (``lib/agents/chat_agent.py``) -- same event mapping, reasoning shown, one
LangGraph thread per conversation -- and talks about documents like the Teams agent
(``lib/agents/teams_agent.py``), from whose prompt the rules on quoting, changing the
document and the missing internet are taken.

What differs from both is where the document comes from. There is no link to open: the
pane sends the document open in Word, as a .docx, whenever it has changed, and it is
mounted at ``DOCUMENT_PATH`` before the turn runs (``pane_document.py``). So the agent
always reads what the person is looking at, unsaved edits included.

No web search, as in Teams: documents here are confidential and the deployment may
allow no outbound requests. Skills are mounted without their web-search consent steps,
and the two that exist only to search the web are left out, as in /chat.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from lib.agents.chat_agent import CHAT_REASONING, EXCLUDED_CHAT_SKILLS
from lib.agents.checkpointer import get_checkpointer
from lib.agents.deep_agent_setup import (
    DEFAULT_MODEL,
    RECURSION_LIMIT,
    build_deep_agent,
    build_llm,
    build_skill_files,
    general_purpose_subagent,
)
from lib.agents.seen_image_redaction import SeenImageRedactionMiddleware
from lib.agents.tools.sharepoint import comments_path, document_files
from lib.agents.tools.view_image import VIEW_IMAGE_PROMPT, view_image_for_conversation
from lib.agents.tools.word_suggestions import (
    DOCUMENT_PATH,
    SuggestionTarget,
    ask_to_apply_for,
    suggest_changes_for,
)
from lib.agents.word_chat_prompt import SYSTEM_PROMPT
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.services.chat.events import ChatEvent, stream_chat_events
from lib.services.chat.history import thread_config
from lib.services.chat.thread_state import READER_API_KEY, load_thread_snapshot
from lib.services.microsoft.graph.documents import LoadedDocument

COMMENTS_PATH = comments_path(DOCUMENT_PATH)

# A selection longer than this is cut: it is a pointer to where they are looking, and
# the whole text is in the document anyway.
MAX_SELECTION_CHARS = 2_000


class WordChatTurn(BaseModel):
    """One message to the agent, and what the pane sent along with it."""

    thread_id: uuid.UUID
    text: str
    message_id: str | None = None
    document: LoadedDocument | None = None
    selection: str | None = None
    suggestion_news: str = ""


def build_word_chat_agent(
    checkpointer: BaseCheckpointSaver,
    target: SuggestionTarget | None = None,
    api_key: str | None = None,
) -> CompiledStateGraph:
    """The agent for one turn. Without a ``target`` it can only be read from."""

    viewing = [view_image_for_conversation(target.chat_thread_id)] if target else []
    return build_deep_agent(
        model=build_llm(
            DEFAULT_MODEL, api_key, reasoning=CHAT_REASONING, output_version="v1"
        ),
        tools=[suggest_changes_for(target), ask_to_apply_for(target), *viewing]
        if target
        else [],
        # A subagent would otherwise get `suggest_changes` too, and what it stores never
        # reaches the conversation the pane shows: cards nobody can see. Subagents read,
        # look at the document's images, and report; the agent makes the suggestions.
        subagents=[{**general_purpose_subagent(skills=["/skills/"]), "tools": viewing}],
        skills=["/skills/"],
        system_prompt=SYSTEM_PROMPT + VIEW_IMAGE_PROMPT,
        middleware=[SeenImageRedactionMiddleware()],
        checkpointer=checkpointer,
    )


def turn_message(turn: WordChatTurn) -> HumanMessage:
    """The message the agent sees: what they typed, then what the pane knows.

    The pane shows only what they typed (``user_text``, as for /chat), so the notes
    about the document, the selection and earlier suggestions stay out of the chat.
    """

    notes: list[str] = []
    if turn.suggestion_news:
        notes.append(turn.suggestion_news)
    if turn.document is not None:
        notes.append(
            f"[The document has been read again for this message, at {DOCUMENT_PATH}: "
            f"{turn.document.lines} lines"
            + (
                f", {len(turn.document.comments)} comments at {COMMENTS_PATH}"
                if turn.document.comments
                else ", no comments"
            )
            + ".]"
        )
    if turn.selection and turn.selection.strip():
        selected = turn.selection.strip()
        if len(selected) > MAX_SELECTION_CHARS:
            selected = selected[:MAX_SELECTION_CHARS].rstrip() + "…"
        notes.append(f"[They have this text selected in Word:\n{selected}]")

    user_text = turn.text.strip()
    return HumanMessage(
        content="\n\n".join(part for part in [user_text, *notes] if part),
        id=turn.message_id or str(uuid.uuid4()),
        additional_kwargs={"user_text": user_text, "attachments": []},
    )


def turn_input(turn: WordChatTurn) -> dict[str, Any]:
    """The graph input: the message, with skills and (when sent) the document mounted.

    Skills are mounted every turn, as /chat does; the files channel merges, so the
    document from an earlier turn stays until a newer copy replaces it.
    """

    files = build_skill_files(exclude=EXCLUDED_CHAT_SKILLS)
    if turn.document is not None:
        files.update(document_files(turn.document, DOCUMENT_PATH))
    return {"files": files, "messages": [turn_message(turn)]}


def run_config(thread_id: uuid.UUID, account_oid: str) -> RunnableConfig:
    """Tracing keyed as the other agents are: one thread, one Langfuse session."""

    return {
        **thread_config(str(thread_id)),
        "run_name": "word_chat_agent",
        "recursion_limit": RECURSION_LIMIT,
        "callbacks": [langfuse_handler, ErrorLoggingCallback()],
        "metadata": {
            "langfuse_tags": ["word-chat"],
            "langfuse_session_id": str(thread_id),
            "langfuse_user_id": account_oid,
        },
    }


async def run_word_chat_turn(
    turn: WordChatTurn, target: SuggestionTarget, api_key: str | None = None
) -> AsyncIterator[ChatEvent]:
    """One turn, as the same events the /chat page renders, checkpointed as it goes.

    ``api_key`` is the person's own OpenAI key; without one the deployment's is used.
    """

    async with get_checkpointer() as saver:
        agent = build_word_chat_agent(saver, target, api_key=api_key)
        async for event in stream_chat_events(
            agent, turn_input(turn), run_config(turn.thread_id, target.requester.oid)
        ):
            yield event


def word_chat_reader(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """This agent's graph, for reading its threads back (``thread_state``)."""

    return build_word_chat_agent(checkpointer, None, api_key=READER_API_KEY)


async def pending_suggestion(thread_id: uuid.UUID) -> uuid.UUID | None:
    """The card a paused conversation is waiting on (``ask_to_apply``), if any."""

    snapshot = await load_thread_snapshot(str(thread_id), reader=word_chat_reader)
    for paused in snapshot.interrupts:
        value = paused.value if isinstance(paused.value, dict) else {}
        try:
            return uuid.UUID(str(value.get("suggestion_id")))
        except ValueError:
            continue
    return None


async def run_word_chat_resume(
    thread_id: uuid.UUID, target: SuggestionTarget, api_key: str | None = None
) -> AsyncIterator[ChatEvent]:
    """Carry on a paused turn once its card is settled, as the same events.

    ``ask_to_apply`` runs again from the top and reads the outcome itself, so the value
    resumed with carries nothing.
    """

    async with get_checkpointer() as saver:
        agent = build_word_chat_agent(saver, target, api_key=api_key)
        async for event in stream_chat_events(
            agent, Command(resume=True), run_config(thread_id, target.requester.oid)
        ):
            yield event
