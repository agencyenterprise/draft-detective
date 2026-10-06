"""Answering a question about a document, in a chat rather than a margin.

Replying inside a Word comment means writing into a pane that renders no markup and
rewards brevity above all. A question asked in Teams is the opposite: it is read in
a chat client, markdown renders, and the useful answer is sometimes a short list
rather than three sentences. So the reply guidance differs enough to warrant its own
prompt.

What does not differ is the construction, which is shared through
``lib/agents/deep_agent_setup.py``: the skills are available, and there is no internet.

**No document is chosen for the agent, and nor is where to put it.** The links found in
the message are handed over as candidates and the agent opens what it needs, via the
tools in ``lib/agents/tools/sharepoint.py``. Which link is meant is a question about the
conversation -- "compare these two", "the second one" -- so it belongs to the agent
rather than to a regex. A link is still the only way in: there is no lookup by name, so a
question naming a document that this thread has not yet opened gets a request for the link.

``graph_token`` is whose reading this run does. Both tools are built from it per run, so
the agent reads with the asker's own access: a document they cannot open is refused by
Graph and the agent says so.

One Teams thread is one LangGraph thread, so a follow-up arrives with the earlier turns
*and the documents opened in them* still in view. Two things follow, and the agent is
told about both: a mounted document may have been edited since it was read, and in a
shared thread it may have been loaded for somebody else. ``check_document`` answers both
in one cheap call -- it reports the edit time, and it fails when the person asking now
cannot reach the document.

Nothing here writes to the document. That is the point of this path -- a question
answered in chat needs no document access at all, which sidesteps both the 423 a
server-side write hits while someone is editing and the licensing questions around
automating a Word client.
"""

import logging
from collections.abc import Sequence
from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes
from pydantic import BaseModel, Field

from lib.agents.checkpointer import get_checkpointer
from lib.agents.deep_agent_setup import (
    DEFAULT_MODEL,
    RECURSION_LIMIT,
    agent_input,
    build_deep_agent,
    build_llm,
    build_skill_files,
    tool_names,
)
from lib.agents.tools.sharepoint import check_document_for, open_document_for
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.config.llm_models import LLMModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Draft Detective, a document review assistant. Someone has asked you a \
question about a Word document from a chat, and you are answering them there.

## The conversation so far

You may be part-way through a conversation. Earlier questions, your own earlier answers, \
and any documents you opened in them are all still here — so look at what you already \
have with `ls` before asking for anything again.

More than one person may be in this thread. Each question says who asked it; answer the \
person asking now, and do not assume they are the person who asked before.

**A document you opened in an earlier turn is a copy, and two things may have changed \
since.** It may have been edited in Word. And it may have been opened for somebody else \
in this thread, who has access the person asking now does not. `check_document(url)` \
settles both cheaply, without downloading anything: it tells you when the document was \
last modified, so you can compare that with the time reported when you opened it, and it \
fails outright if the person asking cannot reach the document.

So before answering from a copy you did not open this turn: check it. If it has been \
edited, open it again to replace it. If the check is refused, say you cannot read that \
document as them — do not answer from the copy you still have, and do not describe its \
contents.

## Getting a document

`open_document(url, path)` opens a document from a SharePoint link and saves it as \
markdown at the path you choose, with any comments beside it. Read or search those files \
with your usual tools; the tool does not hand you the text.

Choose the path, under `/documents/`, and name it after the document — for example, \
`/documents/v3-cern-for-ai.md`. Two documents, or two revisions of one, means two \
different paths, so you can hold both open and tell them apart. Re-opening at the same \
path replaces what is there, which is how you refresh a stale copy.

**A link is the only way to reach a document.** You cannot look one up by name or \
title, and you must not guess at a URL. If someone asks about a document without \
linking to it, say you need the link and ask them to paste it — even when the name \
they used sounds unambiguous. This is deliberate: a link is something they already \
had access to, and searching on their behalf could reach documents they cannot open.

When a message carries links, they are listed for you. Which one is meant is yours to \
work out from what was asked; when it is genuinely unclear, ask rather than guess.

Open a document before answering anything about one. Never answer from a name or a \
file title alone, and never describe content you have not read.

Some questions need no document at all — what you can do, how you work. Answer \
those directly rather than asking for a link you do not need.

## Reading it

A document is markdown, so its structure is visible: `##` headings, tables, and bold or \
highlighted text. Use it to navigate — searching for `"## "` gives you the outline \
before you read anything in full.

Your search tool matches **literal text, not regular expressions**, so `^#` finds \
nothing and `## ` finds every heading. Your read tool numbers the lines it shows you; \
those numbers are for your own navigation, not for the reader, who cannot jump to a \
line number in Word.

## What you can and cannot reach

You can read this document and your own reference material. You have no access to \
the internet, and no way to run commands. This is deliberate: documents reviewed \
here are confidential, and the deployment does not allow outbound requests.

So when a request needs something only the internet could settle, say so plainly \
and stop. Verifying that a DOI resolves, checking whether a paper exists, \
confirming a URL: none of those are possible here. Say which specific check you \
cannot make, and where useful say what in the document would settle it instead. Do \
not guess, and do not imply you looked something up.

## You cannot change the document

You are answering a question, not editing. You cannot add comments, make tracked \
changes, or alter the text from here. If the answer is really a request to change \
something, say what you would change and where, and say plainly that it has to be \
applied in Word.

## Your review expertise

Your capabilities are described as skills under `/skills/`. Consult the ones \
relevant to what has been asked and ignore the rest. A question about a citation, \
for instance, is covered by `/skills/reference-validation/SKILL.md`. Do not read \
every skill; find the ones that apply.

## How to answer

Your last message is posted into the chat as it is, so write the answer itself as \
markdown — no JSON, no wrapper object, no preamble about what you are about to say. A \
list is often clearer than a paragraph. Still write like a colleague who has read the \
document:

- Answer the question that was actually asked. Nothing else.
- Point at places by quoting them, never by numbering them. A short distinctive \
phrase in quotation marks is something the reader can search for in Word; a line number \
is meaningless to them. Naming the section it is under helps; the line it sits on does \
not.
- Be concrete about figures and claims: give the number or the wording you mean, \
not a description of it.
- Length should match the question. A yes-or-no question gets a sentence. "Check \
every citation" gets a list.
- If the document does not settle the question, say so plainly and say what would. \
Never invent a source, a figure or a citation.
- If you are confident something is wrong, say it directly. Hedging wastes time.
"""

REQUEST_PROMPT = """\
{who} asked:

{question}
{links}"""

# Every link found, not one chosen for the agent: which is meant is a question about the
# conversation, and only the agent has that.
ONE_LINK = """
They linked to this document:

{links}"""

MANY_LINKS = """
They linked to these documents:

{links}"""


def links_in(question_urls: Sequence[str]) -> str:
    """The links from the message, as a block for the request prompt."""

    if not question_urls:
        return ""
    listed = "\n".join(f"- {url}" for url in question_urls)
    template = ONE_LINK if len(question_urls) == 1 else MANY_LINKS
    return template.format(links=listed)


def answer_text(messages: Sequence[BaseMessage]) -> str:
    """What the agent said this turn, as markdown. Empty if it said nothing.

    Read from the messages rather than through a structured ``response_format``. The
    answer is one markdown string, and asking for it as JSON made the model escape a
    whole review into a string literal -- tokens spent on backslashes, and a parse to
    fail.

    Stops at the most recent question, which a persisted thread makes load-bearing:
    without it, a turn that produced no text would reach back and re-post the previous
    turn's answer as though it were new.
    """

    for message in reversed(messages):
        if message.type == "human":
            break
        if message.type == "ai" and (text := str(message.text).strip()):
            return text
    return ""


class QuestionAnswer(BaseModel):
    """What the caller gets back, including how it failed if it did."""

    text: str
    model: Optional[str] = None
    steps: int = 0
    tools_used: list[str] = Field(default_factory=list)
    failed: bool = False
    error: Optional[str] = None


async def answer_question(
    question: str,
    graph_token: str,
    thread_id: str,
    document_urls: Optional[Sequence[str]] = None,
    asked_by: str = "Someone",
    model: LLMModel = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    user_id: Optional[str] = None,
) -> QuestionAnswer:
    """Answer a question about a document the agent opens for itself.

    ``graph_token`` is the identity documents are read with: the asker's own, from
    their sign-in to the bot. Required -- there is no other identity to read with.

    ``thread_id`` keys both the checkpoint and the Langfuse session, deliberately under
    one name so a conversation is findable in the trace view under what it is stored as.
    Required: a caller with nothing to continue passes a fresh id rather than opting out.

    ``document_urls`` are the links found in the message, all of them. Candidates rather
    than a decision: which one is meant, and whether to open it at all, depends on what
    was asked and on what the conversation already has open.

    Never raises: a failure comes back as ``failed`` so the caller can decide whether to
    say anything.
    """

    # Langfuse discards propagated metadata that is not a string, so these are
    # stringified rather than silently going missing from the trace.
    urls = list(document_urls or [])
    metadata: dict[str, Any] = {
        "langfuse_tags": ["teams-agent", "document-question"],
        "links_found": str(len(urls)),
        # The same id the checkpoint is keyed by, so a conversation can be found in the
        # trace view under what it is stored as.
        "langfuse_session_id": thread_id,
    }
    if user_id:
        metadata["langfuse_user_id"] = user_id

    run_config: RunnableConfig = {
        "run_name": "teams_agent",
        "recursion_limit": RECURSION_LIMIT,
        "callbacks": [langfuse_handler, ErrorLoggingCallback()],
        "metadata": metadata,
        # The checkpointer and this are a pair: LangGraph refuses a checkpointer with no
        # ``configurable`` to key it by.
        "configurable": {"thread_id": thread_id},
    }

    try:
        async with get_checkpointer() as saver:
            agent = build_deep_agent(
                model=build_llm(model, api_key),
                tools=[
                    open_document_for(graph_token),
                    check_document_for(graph_token),
                ],
                skills=["/skills/"],
                system_prompt=SYSTEM_PROMPT,
                checkpointer=saver,
            )

            prompt = REQUEST_PROMPT.format(
                who=asked_by, question=question.strip(), links=links_in(urls)
            )

            with propagate_attributes(user_id=user_id):
                result = await agent.ainvoke(
                    agent_input(
                        # Skills only. Documents arrive through the tool and stay in the
                        # thread's own files; skills have to be mounted up front because
                        # a tool cannot add them later.
                        files=build_skill_files(),
                        messages=[HumanMessage(content=prompt)],
                    ),
                    config=run_config,
                )
    except Exception as error:  # noqa: BLE001 - the caller decides what to do
        logger.exception("Draft Detective could not answer a question")
        return QuestionAnswer(
            text="", model=model.model_name, failed=True, error=str(error)
        )

    messages = result.get("messages", [])
    text = answer_text(messages)
    if not text:
        logger.warning("the question agent returned an empty answer")
        return QuestionAnswer(
            text="",
            model=model.model_name,
            steps=len(messages),
            tools_used=tool_names(messages),
            failed=True,
            error="the agent returned an empty answer",
        )

    return QuestionAnswer(
        text=text,
        model=model.model_name,
        steps=len(messages),
        tools_used=tool_names(messages),
    )
