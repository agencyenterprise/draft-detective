"""Shared construction for our deep agents.

Every deep agent we run is built with ``build_deep_agent``: ``create_deep_agent``
with our additions, so they live in one place rather than at every call site.

The agents that talk to a user (the chat, the Word add-in's chat and the Teams agent)
also take their model from ``build_llm``, their run config from
``conversation_run_config`` and their skills from ``lib.skills.skill_backend_files``.
Workflow agents get theirs elsewhere: the model from ``LangChainAgent``
(``lib/models/agent.py``), and the skills and document from the workflow itself --
most mount them with ``FileArtifactsService.get_deepagent_backend_files``, the
review assistant mounts its own files beside ``lib.skills.skill_backend_files``, and
Reviewer 2 puts its skill in the system prompt and the document in the message.

``/main.md`` is the document path shared by
``FileArtifactsService.get_deepagent_backend_files`` and the workflow prompts.
Those prompts designate the document used for structured issue line numbers;
the portable ``skills/issues/SKILL.md`` defines the numbering conventions without
requiring a particular document path.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ParamSpec, TypeVar, cast

from deepagents import create_deep_agent
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT, SubAgent
from langchain.agents.middleware import (
    AgentMiddleware,
    InputAgentState,
    TodoListMiddleware,
)
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from lib.agents.read_file_line_numbers import ReadFileLineNumbersMiddleware
from lib.config.env import config, get_model_api_key
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.config.llm_models import LLMModel, gpt_5_6_terra_model
from lib.config.rate_limiter import get_rate_limiter, hash_api_key
from lib.models.agent import ReasoningDict
from lib.services.chat.history import thread_config

logger = logging.getLogger(__name__)

DEFAULT_MODEL = gpt_5_6_terra_model
RECURSION_LIMIT = 60
REQUEST_TIMEOUT = 120

# Medium effort because reviewing a document means reading around it and weighing a
# claim against a source, which is more than a lookup. The summary is surfaced in
# Langfuse, so the reasoning behind an answer can be inspected when one looks wrong.
REASONING: ReasoningDict = {"effort": "medium", "summary": "auto"}


def conversation_run_config(
    thread_id: str,
    *,
    run_name: str,
    tags: Sequence[str],
    user_id: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> RunnableConfig:
    """The run config for one turn of a conversation agent (chat, Word, Teams).

    One id keys both the checkpoint and the Langfuse session, so a conversation is
    found in the trace view under what it is stored as. ``metadata`` adds the
    caller's own trace fields; Langfuse drops propagated values that are not strings.
    """

    trace: dict[str, Any] = {
        **(metadata or {}),
        "langfuse_tags": list(tags),
        "langfuse_session_id": thread_id,
    }
    if user_id:
        trace["langfuse_user_id"] = user_id
    return {
        **thread_config(thread_id),
        "run_name": run_name,
        "recursion_limit": RECURSION_LIMIT,
        "callbacks": [langfuse_handler, ErrorLoggingCallback()],
        "metadata": trace,
    }


def agent_input(
    files: dict[str, Any], messages: Sequence[BaseMessage]
) -> InputAgentState:
    """A deep agent's input: its conversation plus the files mounted for it.

    `files` is the filesystem middleware's state. The runtime takes it, but the
    compiled graph types its input as LangChain's `InputAgentState`, which only
    declares `messages`, hence the cast.
    """
    return cast(InputAgentState, {"files": files, "messages": list(messages)})


def agent_middleware() -> list[AgentMiddleware[Any, Any, Any]]:
    """The middleware every deep agent of ours runs, and every subagent it delegates to.

    `TodoListMiddleware` gives the agent its `write_todos` planning tool. deepagents
    included it by default until 0.7, so it is added back here.
    """
    return [TodoListMiddleware(), ReadFileLineNumbersMiddleware()]


def general_purpose_subagent(skills: list[str] | None = None) -> SubAgent:
    """deepagents' general-purpose subagent, running our middleware as well.

    Replaces the default one: deepagents builds that with its own default
    middleware only, so a parent's middleware never reaches delegated work.
    Takes the parent's `skills`, which the default subagent also gets.
    """
    spec: SubAgent = {**GENERAL_PURPOSE_SUBAGENT, "middleware": agent_middleware()}
    if skills is not None:
        spec["skills"] = skills
    return spec


def _running_our_middleware(spec: Mapping[str, Any]) -> Mapping[str, Any]:
    """A caller's subagent spec with our middleware ahead of its own.

    deepagents builds a declared subagent with its own default stack plus the
    spec's middleware, so without this it would miss ours. A precompiled subagent
    (one with a `runnable`) is used as given, since its middleware was fixed when
    it was built. A kind of middleware the spec already runs is not added twice.
    """
    if "runnable" in spec:
        return spec
    own = list(spec.get("middleware") or ())
    kinds = {type(m) for m in own}
    ours = [m for m in agent_middleware() if type(m) not in kinds]
    return {**spec, "middleware": [*ours, *own]}


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _with_our_additions(create: Callable[_P, _R]) -> Callable[_P, _R]:
    def build(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        # The ParamSpec types every keyword argument as `object`; these are the
        # types `create_deep_agent` declares for the three it reads.
        middleware = cast(
            Sequence[AgentMiddleware[Any, Any, Any]], kwargs.get("middleware") or ()
        )
        declared = cast(Sequence[Mapping[str, Any]], kwargs.get("subagents") or ())
        subagents = [_running_our_middleware(spec) for spec in declared]
        skills = cast(list[str] | None, kwargs.get("skills"))
        kwargs["middleware"] = [*agent_middleware(), *middleware]
        if not any(
            spec.get("name") == GENERAL_PURPOSE_SUBAGENT["name"] for spec in subagents
        ):
            subagents.append(general_purpose_subagent(skills=skills))
        kwargs["subagents"] = subagents
        return create(*args, **kwargs)

    return build


build_deep_agent = _with_our_additions(create_deep_agent)
"""``create_deep_agent``, same signature, with our middleware added to the caller's
and to every subagent the caller declares, and the general-purpose subagent replaced
by ours (unless the caller passes one)."""


def has_deployment_key(model: LLMModel) -> bool:
    """Whether ``model`` can run without a user's own key: the deployment set one."""

    return bool(get_model_api_key(model.name) or config.OPENAI_API_KEY)


def build_llm(
    model: LLMModel,
    api_key: str | None,
    *,
    reasoning: ReasoningDict = REASONING,
    output_version: str | None = None,
) -> BaseChatModel:
    """The construction LangChainAgent uses for an OpenAI model, including the shared
    rate limiter.

    OpenAI only: ``reasoning`` is passed in OpenAI's terms, where LangChainAgent
    translates it for Claude.

    ``output_version`` selects how langchain-openai lays out the message content.
    The web and Word chat agents ask for ``"v1"``: under the default layout, streamed
    reasoning summaries and hosted web-search calls do not reach
    ``stream_mode="messages"`` consumers, while ``v1`` surfaces them as ``reasoning``
    and ``server_tool_call`` content blocks. The Teams agent keeps the default and
    never reads them.
    """

    resolved = api_key
    if resolved is None and model.provider == "openai":
        resolved = get_model_api_key(model.name)

    kwargs: dict[str, Any] = {
        "model": model.model_name,
        "timeout": REQUEST_TIMEOUT,
        "max_retries": 4,
        "rate_limiter": get_rate_limiter(hash_api_key(resolved or "default")),
        "reasoning": reasoning,
    }
    if resolved:
        kwargs["api_key"] = resolved
    if output_version:
        kwargs["output_version"] = output_version
    return init_chat_model(**kwargs)


def tool_names(messages: list[Any]) -> list[str]:
    """Which tools a run actually called, for the caller's own reporting."""

    used: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else None
            if name:
                used.append(name)
    return sorted(set(used))
