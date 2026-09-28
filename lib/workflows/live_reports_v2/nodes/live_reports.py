"""Live reports v2 node — runs a simple deep agent with web search.

Mirrors the v1 Live Reports goal (find sources published *after* the document's
publication date that update or challenge its claims, and produce an addendum)
but is implemented with the simple deep-agent pattern: the agent reads the
document from `/main.md` via its tools, writes its markdown report to
`/report.md`, and reports issues through validated tool calls.
"""

import logging
from datetime import date

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import format_bibliography
from lib.config.llm_models import web_search_tool
from lib.skills import load_skill_prompt
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.agent_types import markdown_result_from_run
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

logger = logging.getLogger(__name__)


class LiveReportsV2Agent(SimpleDeepAgent):
    """Simple deep agent with a longer timeout for the web-search-heavy
    live reports pass."""

    timeout = 600


# The live-report *procedure* is the portable `live-reports` skill (the single
# source of truth). This system prompt carries only the Draft-Detective-specific
# framing: where the document lives and how to map the skill's recommendations
# onto the standard issues output contract.
_SYSTEM_PROMPT = """\
You are an expert research analyst producing a "live report" addendum for a document.

## Document

The document is available at `/main.md`. Use your tools to read or search its \
content as needed. Use web search to find newer literature that may update or \
challenge the document's claims.

## Reporting

Follow the issue-reporting conventions in the issues skill \
(`/skills/issues/SKILL.md`) and call `report_issue` once per claim that newer \
evidence would update or strengthen. For each update, explain what the newer \
evidence shows and whether it supports, conflicts with, or contextualizes the \
claim; include the full citation, URL/DOI, relevant finding, relationship to the \
claim, and a concrete action. Ground the issue at the affected passage. Use \
medium severity for an actionable update or added citation and low for a purely \
contextual addition.

Write an overall addendum summarizing the most important updates, with the full \
citation for every recommended source, to `/report.md` using `write_file`. This \
file is the report deliverable; write it in full. Report every update by calling \
`report_issue`; if nothing warrants an update, make no issue calls and write a \
short report saying so. Nothing in your final message is used as the report or \
issue list.\
"""


# Backend-injected, per-run inputs appended to the portable skill prompt.
_INPUTS_TEMPLATE = """\

---

## Inputs for this run

### Document publication date
{document_publication_date}

### Current bibliography from the document (already cited — do not re-list these)
```
{bibliography}
```
"""


@register_node("Generate live report")
async def live_reports(
    state: SimpleDeepAgentState, runtime: Runtime[ContextSchema]
) -> dict:
    file_artifacts_service = runtime.context.file_artifacts_service

    references = await file_artifacts_service.get_extracted_references()
    bibliography = format_bibliography(references)
    document_publication_date = (
        state.config.publication_date
        if state.config.publication_date
        else date.today().isoformat()
    )

    user_prompt = load_skill_prompt("live-reports") + _INPUTS_TEMPLATE.format(
        document_publication_date=document_publication_date,
        bibliography=bibliography,
    )

    agent = LiveReportsV2Agent(
        context=runtime.context,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tools=[web_search_tool(runtime.context.agent_model(LiveReportsV2Agent.model))],
    )
    run = await agent.ainvoke({})

    return {"result": markdown_result_from_run(run), "messages": run.messages}
