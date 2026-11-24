"""Which agent each kind of ``chat_threads`` row talks to.

/chat and /live-reports share the thread tables, the checkpointer and the turn loop
(``run_chat_turn``). What differs is the agent, its input and its tracing, and the
graph a thread's state is read back through: always the one that wrote it.
"""

from pydantic import BaseModel, ConfigDict

from lib.agents.chat_agent import (
    DEFAULT_CHAT_MODEL,
    AgentBuilder,
    InputBuilder,
    RunConfigBuilder,
    build_chat_agent,
    build_chat_input,
    chat_reader,
    chat_run_config,
)
from lib.agents.live_report_agent import (
    LIVE_REPORT_DEFAULT_MODEL,
    build_live_report_agent,
    build_live_report_input,
    live_report_reader,
    live_report_run_config,
)
from lib.config.llm_models import LLMModel
from lib.models.chat_thread import ChatThreadKind
from lib.services.chat.thread_state import ThreadReader


class ThreadAgent(BaseModel):
    """What a turn and a read of one kind of thread need."""

    model_config = ConfigDict(frozen=True)

    build_agent: AgentBuilder
    build_input: InputBuilder
    run_config: RunConfigBuilder
    reader: ThreadReader
    default_model: LLMModel


THREAD_AGENTS: dict[ChatThreadKind, ThreadAgent] = {
    ChatThreadKind.CHAT: ThreadAgent(
        build_agent=build_chat_agent,
        build_input=build_chat_input,
        run_config=chat_run_config,
        reader=chat_reader,
        default_model=DEFAULT_CHAT_MODEL,
    ),
    ChatThreadKind.LIVE_REPORT: ThreadAgent(
        build_agent=build_live_report_agent,
        build_input=build_live_report_input,
        run_config=live_report_run_config,
        reader=live_report_reader,
        default_model=LIVE_REPORT_DEFAULT_MODEL,
    ),
}


def thread_agent(kind: ChatThreadKind | str) -> ThreadAgent:
    """The agent for a thread's kind; rows store the kind as a plain string."""

    return THREAD_AGENTS[ChatThreadKind(kind)]
