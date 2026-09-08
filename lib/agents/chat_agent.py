"""The agent behind the /chat page.

A third consumer of ``lib/agents/deep_agent_setup.py``, next to the Word and Teams
agents. Same model construction, same rate limiter, same skills mounted into the
same virtual filesystem, so a chat answer and a workflow run on the same question
reason from the same instructions.

Like the Teams agent, one chat thread is one LangGraph thread: the conversation,
the agent's filesystem (attached documents included) and its tool results live
in the shared Postgres checkpointer, keyed by the ``chat_threads`` row id. A turn
therefore carries only the new message. See ``lib/services/chat/history.py`` for
how the state is read back and shown.

Two things are particular to the chat:

- **Skills keep their interactive sections.** There is a user to ask, so the
  web-search consent steps apply here rather than being stripped.
- **The model streams reasoning and hosted tool calls.** ``output_version="v1"``
  and a ``detailed`` summary are what make them visible through
  ``stream_mode="messages"``; see ``build_llm``.
"""

from typing import Any, AsyncIterator, Optional, Sequence

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from lib.agents.checkpointer import get_checkpointer
from lib.agents.deep_agent_setup import RECURSION_LIMIT, build_llm, build_skill_files
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.config.llm_models import (
    LLMModel,
    gpt_5_6_luna_model,
    gpt_5_6_sol_model,
    gpt_5_6_terra_model,
    web_search_tool,
)
from lib.models.agent import ReasoningDict
from lib.services.chat.events import ChatEvent, stream_chat_events
from lib.services.chat.history import ChatAttachment, build_user_turn, thread_config
from lib.skills import SkillSummary, list_skill_summaries
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_all_manifests


class ChatModelOption(BaseModel):
    """One entry of the page's model picker."""

    model: LLMModel
    name: str

    @property
    def id(self) -> str:
        return self.model.name


# Terra first: it is the default because it is what every backend agent runs on.
CHAT_MODELS: tuple[ChatModelOption, ...] = (
    ChatModelOption(model=gpt_5_6_terra_model, name="GPT-5.6 Terra"),
    ChatModelOption(model=gpt_5_6_luna_model, name="GPT-5.6 Luna"),
    ChatModelOption(model=gpt_5_6_sol_model, name="GPT-5.6 Sol"),
)
DEFAULT_CHAT_MODEL = CHAT_MODELS[0].model

# These two go looking for new literature rather than reviewing a draft the
# author already has, which is a different product. Their SKILL.md files stay on
# disk for the workflows; they are just not offered in the chat.
EXCLUDED_CHAT_SKILLS = frozenset({"literature-review", "live-reports"})

# The workflow each chat skill is the batch form of. A skill's slash-command
# description is taken from that manifest, so the two never drift apart; skills
# without a workflow (helpers such as `issues` or `voice-and-tone`) keep the
# description in their own SKILL.md. Curated rather than derived, because the
# relation is not one-to-one: `about_this_ger` backs two skills, and the
# `review-assistant` skill is a companion to three workflows rather than a check.
SKILL_WORKFLOWS: dict[str, WorkflowRunType] = {
    "abbreviation-scan": WorkflowRunType.ABBREVIATION_SCAN_V2,
    "about-this-authors": WorkflowRunType.ABOUT_THIS_GER,
    "about-this-preface": WorkflowRunType.ABOUT_THIS_GER,
    "advocacy-tone": WorkflowRunType.ADVOCACY_TONE_V2,
    "citation-support": WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
    "document-contents": WorkflowRunType.DOCUMENT_STRUCTURE,
    "figures-tables-check": WorkflowRunType.FIGURES_TABLES_CHECK,
    "inference-validation": WorkflowRunType.INFERENCE_VALIDATION_V2,
    "methodology-comparison": WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
    "recommendation-check": WorkflowRunType.RECOMMENDATION_CHECK,
    "reference-download": WorkflowRunType.REFERENCE_DOWNLOADER,
    "reference-extraction": WorkflowRunType.REFERENCE_EXTRACTION,
    "reference-validation": WorkflowRunType.REFERENCE_VALIDATION_V2,
    "reproducibility-check": WorkflowRunType.RESULTS_EXTRACTION,
    "reviewer-2": WorkflowRunType.REVIEWER_2,
}

# ``detailed`` rather than ``auto``: on gpt-5.6-terra ``auto`` produced no
# summary text at all in testing, which would leave the chain-of-thought panel
# empty. Even ``detailed`` is best-effort; short turns may still show nothing.
CHAT_REASONING: ReasoningDict = {"effort": "medium", "summary": "detailed"}

SYSTEM_PROMPT = """\
You are Draft Detective, an AI assistant specialized in peer review of academic \
papers and policy research.

Your purpose is to help researchers, analysts, and reviewers assess and improve \
manuscripts and policy reports before formal peer review. You focus on the \
substance of the work: the soundness of claims and citations, the validity of \
reasoning and methodology, the accuracy of references, the completeness and \
consistency of structure, figures, and tables, and the clarity and neutrality of \
the writing.

How you work:
- Be rigorous, precise, and candid, but constructive: a clearly identified \
weakness is a gift to the author.
- Ground every judgment in the text the user provides. Do not invent findings, \
sources, or quotations. If you need the document (or a specific section) and it \
has not been provided, ask for it.
- Documents the user attaches are mounted in your filesystem under \
`/attachments/`, and the message that attached one names its path. Read them \
with your file tools; `grep` and `read_file` with an offset let you work through \
a long document without loading all of it. Everything opened in earlier turns is \
still there, so check `ls /attachments` before asking for a document again. When \
you make claims about a document, cite the specific passages you are relying on: \
quote them, and name the file and line numbers in plain prose, for example \
(draft.md, lines 12–18). There is no citation tool here, so never emit citation \
markup or special citation tokens; write the reference as ordinary text.
- You can search the web with the `web_search` tool. Use it to find current \
information and to locate and verify sources, references, and related \
literature, and cite the URLs you rely on. Do not rely on memory for factual \
claims about real-world sources.
- Web search sends the user's text to an external provider, so a check that \
searches on their document needs their explicit consent first. The skills that \
do this (`reference-validation`, `reference-download`, `methodology-comparison`) \
open with the consent step and the wording to relay. Follow it, and wait for an \
explicit yes before the first search. One consent covers that document for the \
rest of the conversation. Searching for general background that carries no \
document content does not need it.
- Keep general conversation helpful and on-topic for peer review and research \
quality.

Your review expertise is described as skills under `/skills/`, one per directory, \
each with the full expert instructions in `/skills/<name>/SKILL.md`. When a \
user's request matches a skill, read that file with your file tools before \
starting, then follow it precisely. You may read more than one when a task calls \
for it (some skills reference others). Never act on a skill from memory: always \
read it first.

One of them, `voice-and-tone`, governs how you write rather than what to check. \
Read it before drafting anything substantial that a person will read (findings, a \
review, a memo, a summary, recommendations, an answer explaining what is wrong \
with a draft) and follow it for the wording. A short factual reply or a \
clarifying question does not need it. Where a task skill specifies content, \
structure, or formatting, that skill wins; `voice-and-tone` governs the wording.

Your final message is shown to the user as markdown. Write the answer itself, \
with no preamble about what you are about to do.\
"""


def chat_skill_catalogue() -> list[SkillSummary]:
    """The skills the chat offers, described the way the workflow picker is.

    Ordered by name, as on disk. A workflow that has been retired (no manifest
    registered) falls back to the skill's own description rather than dropping
    the skill.
    """

    manifests = get_all_manifests()
    catalogue: list[SkillSummary] = []
    for skill in list_skill_summaries(exclude=EXCLUDED_CHAT_SKILLS):
        workflow_type = SKILL_WORKFLOWS.get(skill.name)
        manifest = manifests.get(workflow_type) if workflow_type else None
        description = manifest.description if manifest else skill.description
        catalogue.append(SkillSummary(name=skill.name, description=description))
    return catalogue


def resolve_chat_model(model_id: Optional[str]) -> LLMModel:
    """The allowlisted model for an id, or the default for anything else.

    Falls back rather than failing so an old client, or a picker that still names
    a retired model, keeps working. The route can never be driven to an arbitrary
    model this way.
    """

    for option in CHAT_MODELS:
        if option.id == model_id:
            return option.model
    return DEFAULT_CHAT_MODEL


def build_chat_agent(
    model: LLMModel, api_key: Optional[str], checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    """A fresh agent for one turn over a durable thread: skills and web search bound."""

    return create_deep_agent(
        model=build_llm(
            model, api_key, reasoning=CHAT_REASONING, output_version="v1"
        ),
        tools=[web_search_tool(model)],
        skills=["/skills/"],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def build_chat_input(message: HumanMessage, files: dict[str, Any]) -> dict[str, Any]:
    """The graph input for a turn: the new message, with skills and attachments mounted.

    Skills are mounted every turn, as the Teams agent does: the files channel
    merges, so this refreshes them without touching what the thread already holds.
    """

    return {
        "files": {**build_skill_files(interactive=True, exclude=EXCLUDED_CHAT_SKILLS), **files},
        "messages": [message],
    }


def chat_run_config(thread_id: str, user_id: str) -> RunnableConfig:
    """Tracing keyed the same way the Teams agent is: one thread, one session."""

    return {
        **thread_config(thread_id),
        "run_name": "chat_agent",
        "recursion_limit": RECURSION_LIMIT,
        "callbacks": [langfuse_handler, ErrorLoggingCallback()],
        "metadata": {
            "langfuse_tags": ["chat"],
            "langfuse_session_id": thread_id,
            "langfuse_user_id": user_id,
        },
    }


async def run_chat_turn(
    *,
    thread_id: str,
    user_id: str,
    model: LLMModel,
    api_key: Optional[str],
    text: str,
    attachments: Sequence[ChatAttachment] = (),
    message_id: Optional[str] = None,
) -> AsyncIterator[ChatEvent]:
    """One turn of a thread, as the page's events, checkpointed as it goes."""

    message, files = build_user_turn(text, attachments, message_id)
    async with get_checkpointer() as saver:
        agent = build_chat_agent(model, api_key, saver)
        async for event in stream_chat_events(
            agent, build_chat_input(message, files), chat_run_config(thread_id, user_id)
        ):
            yield event
