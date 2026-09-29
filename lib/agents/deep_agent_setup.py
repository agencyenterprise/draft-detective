"""Shared construction for the deep agents that review a document directly.

Two agents work on a Word document without a project or a database behind them: the
one answering a comment from the add-in, and the one answering a question from Teams.
They differ in their prompts, their tools and what they return, but they are built
the same way -- same model construction, same rate limiter, same skills mounted into
the same virtual filesystem.

That construction lives here rather than in either agent. It was in ``word_agent``
first and the Teams agent imported it from there, which had the dependency the wrong
way round: answering a question in a chat has nothing to do with Word comments, and
one agent should not be the other's utility library.

Every deep agent we run is built with ``build_deep_agent``: ``create_deep_agent``
with our additions, so they live in one place rather than at every call site.

``/main.md`` is the document path shared by ``build_agent_files``,
``FileArtifactsService.get_deepagent_backend_files`` and the workflow prompts.
Those prompts designate the document used for structured issue line numbers;
the portable ``skills/issues/SKILL.md`` defines the numbering conventions without
requiring a particular document path.
"""

import logging
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, Optional, ParamSpec, TypeVar, cast

from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT, SubAgent
from langchain.agents.middleware import AgentMiddleware, InputAgentState, TodoListMiddleware
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.messages import BaseMessage

from lib.agents.read_file_line_numbers import ReadFileLineNumbersMiddleware
from lib.config.env import get_model_api_key
from lib.config.llm_models import LLMModel, gpt_5_6_terra_model
from lib.config.rate_limiter import get_rate_limiter, hash_api_key
from lib.models.agent import ReasoningDict
from lib.skills import strip_interactive_markers, strip_interactive_only

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]
SKILLS_DIR = PROJECT_ROOT / "skills"

DEFAULT_MODEL = gpt_5_6_terra_model
RECURSION_LIMIT = 60
REQUEST_TIMEOUT = 120

# Medium effort because reviewing a document means reading around it and weighing a
# claim against a source, which is more than a lookup. The summary is surfaced in
# Langfuse, so the reasoning behind an answer can be inspected when one looks wrong.
REASONING: ReasoningDict = {"effort": "medium", "summary": "auto"}


def number_paragraphs(paragraphs: list[str]) -> str:
    """The document as the agent sees it, each paragraph prefixed with its index.

    Numbering is what lets an annotation point at a place instead of describing it.
    The indices come from the caller's own paragraph list, so they are an exact
    handle back to the paragraph rather than something to search for. The same idea
    as the sentinels the docx export injects, which exist to avoid fuzzy matching.
    """

    return "\n\n".join(f"[{index}] {text}" for index, text in enumerate(paragraphs))


def build_skill_files(
    *, interactive: bool = False, exclude: Collection[str] = ()
) -> dict[str, Any]:
    """Mount the project's skills into the agent's filesystem.

    Separate from the document because skills can only be mounted before the run:
    the skills middleware reads them once and skips thereafter, so an agent that
    opens its document mid-run still needs these up front.

    Interactive-only sections (e.g. asking the user for web-search consent)
    address an agent driven by a user. A backend run has its consent already and
    nobody to ask, so by default they are removed; an agent that talks to a user
    passes ``interactive=True`` to keep them, minus the marker comments.
    ``exclude`` names skill directories to leave out of the mount entirely.
    """

    clean = strip_interactive_markers if interactive else strip_interactive_only
    files: dict[str, Any] = {}
    for path in sorted(SKILLS_DIR.rglob("*")):
        if not path.is_file() or path.relative_to(SKILLS_DIR).parts[0] in exclude:
            continue
        virtual_path = "/" + path.relative_to(PROJECT_ROOT).as_posix()
        files[virtual_path] = create_file_data(clean(path.read_text(encoding="utf-8")))
    return files


def agent_input(files: dict[str, Any], messages: Sequence[BaseMessage]) -> InputAgentState:
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
        middleware = cast(Sequence[AgentMiddleware[Any, Any, Any]], kwargs.get("middleware") or ())
        declared = cast(Sequence[Mapping[str, Any]], kwargs.get("subagents") or ())
        subagents = [_running_our_middleware(spec) for spec in declared]
        skills = cast(Optional[list[str]], kwargs.get("skills"))
        kwargs["middleware"] = [*agent_middleware(), *middleware]
        if not any(spec.get("name") == GENERAL_PURPOSE_SUBAGENT["name"] for spec in subagents):
            subagents.append(general_purpose_subagent(skills=skills))
        kwargs["subagents"] = subagents
        return create(*args, **kwargs)

    return build


build_deep_agent = _with_our_additions(create_deep_agent)
"""``create_deep_agent``, same signature, with our middleware added to the caller's
and to every subagent the caller declares, and the general-purpose subagent replaced
by ours (unless the caller passes one)."""


def build_agent_files(document_text: str) -> dict[str, Any]:
    """Mount the document and the project's skills into the agent's filesystem.

    Mirrors ``FileArtifactsService.get_deepagent_backend_files`` without needing a
    project or a database.
    """

    return {"/main.md": create_file_data(document_text), **build_skill_files()}


def build_llm(
    model: LLMModel,
    api_key: Optional[str],
    *,
    reasoning: ReasoningDict = REASONING,
    output_version: Optional[str] = None,
) -> BaseChatModel:
    """Same construction LangChainAgent uses, including the shared rate limiter.

    ``output_version`` selects how langchain-openai lays out the message content.
    The chat agent asks for ``"v1"``: under the default layout, streamed reasoning
    summaries and hosted web-search calls do not reach ``stream_mode="messages"``
    consumers, while ``v1`` surfaces them as ``reasoning`` and ``server_tool_call``
    content blocks. Batch agents keep the default and never read them.
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
