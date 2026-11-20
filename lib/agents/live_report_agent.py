"""The agent behind the /live-reports page: a lean orchestrator over /chat's threads.

A live report is one long conversation that brings a published report up to date,
guided by the portable ``live-reports`` skill: intake, research plan, research,
research brief, then an addendum, a change plan or both, with the user approving
each step. It runs on /chat's
machinery (``chat_threads``, the checkpointer, ``run_chat_turn``, the same events);
only the agent differs, chosen by the thread's kind in ``thread_agents.py``.

The orchestrator talks to the user and decides what happens next. It holds no web
search of its own: the research runs in ``researcher`` subagents, one per fact, data
source and angle of the plan, in parallel, and the brief and the addendum in a ``synthesizer``. Subagents share the
thread's filesystem, so their notes land under ``/live-report/research/`` without
passing through the orchestrator's context; they reply in a few lines.

Only the skills this flow uses are mounted (``LIVE_REPORT_SKILLS``), so the
orchestrator's filesystem and prompt stay small.
"""

from datetime import UTC, datetime
from typing import Any

from deepagents.middleware.filesystem import FilesystemPermission
from deepagents.middleware.subagents import SubAgent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from lib.agents.chat_agent import CHAT_REASONING
from lib.agents.deep_agent_setup import (
    build_deep_agent,
    build_llm,
    conversation_run_config,
)
from lib.agents.research_guard import ResearchGuardMiddleware
from lib.config.llm_models import LLMModel, gpt_5_6_sol_model, web_search_tool
from lib.services.chat.thread_state import READER_API_KEY
from lib.skills import skill_backend_files

# Where the skill's files go in the thread's filesystem; the viewer reads them here.
LIVE_REPORT_DIR = "/live-report"

# The skills a live report mounts: the flow itself, and how to write.
LIVE_REPORT_SKILLS = frozenset({"live-reports", "voice-and-tone"})

# The orchestrator's model when the picker names none. Sol rather than /chat's Terra:
# a live report is long, multi-step work where the stronger model pays off.
LIVE_REPORT_DEFAULT_MODEL = gpt_5_6_sol_model

SYSTEM_PROMPT = f"""\
You help the user bring a published report up to date, following the \
`live-reports` skill. Read `/skills/live-reports/SKILL.md` before your first \
reply in a conversation, and read each step's instructions under \
`/skills/live-reports/steps/` when that step starts. Follow them precisely.

- The report is attached under `/attachments/`; the message that attached it \
names its path. Read it with your file tools; `grep` and `read_file` with an \
offset let you work through a long report.
- Write every file the skill names under `{LIVE_REPORT_DIR}/` \
(`{LIVE_REPORT_DIR}/intake.md`, `{LIVE_REPORT_DIR}/research-plan.md`, and so on). \
The user sees these files beside the conversation, so edit them in place and \
never keep a second copy.
- You have no web search. Research runs in the `researcher` subagent: start one \
per fact, data source and angle of the approved plan (claims aren't \
researched), all in the same response so they run in parallel, \
and give each the item, the report's title, the cutoff that applies to the item \
(see the plan's time window), the plan's source guidance and the path for its \
notes (`{LIVE_REPORT_DIR}/research/<item id>.md`). Then hand the plan, the notes \
and the report's path to the `synthesizer` subagent for the brief. For an \
addendum, hand the `synthesizer` the intake, the approved brief, the report's path \
and the user's answers, and name `steps/addendum.md`; when the user wants both outputs, \
start it before writing the change plan yourself, so they run in parallel.
- Stay lean: don't read the research notes yourself unless the user asks about \
an item. Work from the subagents' short replies and the brief.

Your messages are shown to the user as markdown. Keep them short: the files hold \
the detail.\
"""

RESEARCHER_PROMPT = f"""\
You research one fact, data source or angle of a live report's research plan: \
what has changed between the cutoff you are given for it and today ({{today}}). Confirming that the item was true \
when the report was written adds nothing; find out whether it is still true now. \
Read `/skills/live-reports/steps/research.md` first and follow it exactly. Use the \
`web_search` tool to find and read sources. Write your notes to the path you are \
given under `{LIVE_REPORT_DIR}/research/`, and touch no other file. Reply in at \
most three lines, as the instructions say.\
"""


def researcher_prompt(today: datetime) -> str:
    """The researcher's prompt, dated: "today" has to mean the day of the run."""

    return RESEARCHER_PROMPT.format(today=f"{today:%B} {today.day}, {today.year}")


SYNTHESIZER_PROMPT = f"""\
You write one of a live report's documents, whichever you are asked for, and \
touch no other file. Read `/skills/voice-and-tone/SKILL.md` first, then the \
step's instructions, and follow them. Reply in one line, as they say.

- The research brief: follow `/skills/live-reports/steps/research-brief.md`. Read \
the research plan, the report at the path you are given, and the note under \
`{LIVE_REPORT_DIR}/research/` for each item in it, then write `{LIVE_REPORT_DIR}/research-brief.md`, using only what those notes \
contain. A note for an item the plan no longer has, or one you are told is stale, \
doesn't count.
- The addendum: follow `/skills/live-reports/steps/addendum.md`. Read the intake, \
the report at the path you are given, the approved `{LIVE_REPORT_DIR}/research-brief.md` and the user's answers you are \
given, then write `{LIVE_REPORT_DIR}/addendum.md`, using only what the brief \
contains.\
"""


# What each subagent may touch, enforced by the file tools rather than asked of the
# model: a web page a researcher reads can carry instructions. A researcher writes
# only its notes and can't read the report, so a page can't make it leak the report
# or change a file the user approved. First match wins; anything else is allowed.
RESEARCHER_PERMISSIONS = [
    FilesystemPermission(operations=["read"], paths=["/attachments/**"], mode="deny"),
    FilesystemPermission(
        operations=["write"], paths=[f"{LIVE_REPORT_DIR}/research/**"], mode="allow"
    ),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
]
SYNTHESIZER_PERMISSIONS = [
    FilesystemPermission(
        operations=["write"],
        paths=[
            f"{LIVE_REPORT_DIR}/research-brief.md",
            f"{LIVE_REPORT_DIR}/addendum.md",
        ],
        mode="allow",
    ),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
]


def live_report_subagents(model: LLMModel) -> list[SubAgent]:
    """The helpers the orchestrator delegates to; only the researcher can search."""

    return [
        {
            "name": "researcher",
            "description": (
                "Researches ONE fact, data source or angle (F…, D…, A…) of the "
                "approved research plan on the web and writes its notes; claims "
                "aren't researched. Give it the item as written in the plan, the "
                "report's title, the item's cutoff, the plan's source guidance and "
                "the path for its notes. Start one per such item, in parallel."
            ),
            "system_prompt": researcher_prompt(datetime.now(UTC)),
            "tools": [web_search_tool(model)],
            "permissions": RESEARCHER_PERMISSIONS,
        },
        {
            "name": "synthesizer",
            "description": (
                "Writes one document: the research brief from the research notes, "
                "once every researcher has finished, or the addendum from the "
                "approved brief. Say which, and pass the user's answers."
            ),
            "system_prompt": SYNTHESIZER_PROMPT,
            "tools": [],
            "permissions": SYNTHESIZER_PERMISSIONS,
        },
    ]


def build_live_report_agent(
    model: LLMModel, api_key: str | None, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    """A fresh orchestrator for one turn over a durable thread."""

    return build_deep_agent(
        model=build_llm(model, api_key, reasoning=CHAT_REASONING, output_version="v1"),
        tools=[],
        middleware=[ResearchGuardMiddleware(f"{LIVE_REPORT_DIR}/research")],
        subagents=live_report_subagents(model),
        skills=["/skills/"],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def live_report_reader(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """This agent's graph, for reading its threads back (``thread_state``)."""

    return build_live_report_agent(
        LIVE_REPORT_DEFAULT_MODEL, READER_API_KEY, checkpointer
    )


def build_live_report_input(
    message: HumanMessage, files: dict[str, Any]
) -> dict[str, Any]:
    """The graph input for a turn: the new message, with this flow's skills mounted.

    Interactive, as in /chat: there is a user to ask for web-search consent.
    """

    return {
        "files": {
            **skill_backend_files(interactive=True, include=LIVE_REPORT_SKILLS),
            **files,
        },
        "messages": [message],
    }


def live_report_run_config(thread_id: str, user_id: str) -> RunnableConfig:
    """Traced like /chat's turns, under this agent's own name and tag."""

    return conversation_run_config(
        thread_id, run_name="live_report_agent", tags=["live_report"], user_id=user_id
    )
