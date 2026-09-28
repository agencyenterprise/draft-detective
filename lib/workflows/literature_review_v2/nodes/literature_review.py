"""Literature review v2 node — runs a simple deep agent with web search.

Mirrors the v1 literature review goal (surface relevant academic sources the
document may have missed, both supporting and conflicting) but is implemented
with the simple deep-agent pattern: the agent reads the document from `/main.md`
via its tools, writes its markdown report to `/report.md`, and reports issues
through validated tool calls.
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


class LiteratureReviewV2Agent(SimpleDeepAgent):
    """Simple deep agent with a longer timeout for the web-search-heavy
    literature review pass."""

    timeout = 600


# The literature-review *procedure* is the portable `literature-review` skill
# (the single source of truth). This system prompt carries only the
# Draft-Detective-specific framing: where the document lives and how to map the
# skill's recommendations onto the standard issues output contract.
_SYSTEM_PROMPT = """\
You are an expert literature review researcher reviewing a document.

## Document

The document is available at `/main.md`. Use your tools to read or search its \
content as needed. Use web search to find high-quality academic sources.

## Reporting

Follow the issue-reporting conventions in the issues skill \
(`/skills/issues/SKILL.md`) and call `report_issue` once per recommended source. \
For each recommendation, explain the source's quality and whether it supports, \
conflicts with, or contextualizes the document; include its full citation, \
URL/DOI, relevant source and document excerpts, and a concrete action. Ground \
the issue at the related passage. Use low severity by default and medium only \
when a missing or conflicting source is clearly significant.

Write an overall report summarizing the review by topic, with the full citation \
for every recommended source, to `/report.md` using `write_file`. This file is \
the report deliverable; write it in full. Report every recommended source by \
calling `report_issue`; if there are no recommendations, make no issue calls. \
Nothing in your final message is used as the report or issue list.\
"""


# Backend-injected, per-run inputs appended to the portable skill prompt.
_INPUTS_TEMPLATE = """\

---

## Inputs for this run

### Document publication date
{document_publication_date}

### Extracted bibliography
```
{bibliography}
```
"""


@register_node("Review literature")
async def literature_review(
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

    user_prompt = load_skill_prompt("literature-review") + _INPUTS_TEMPLATE.format(
        document_publication_date=document_publication_date,
        bibliography=bibliography,
    )

    agent = LiteratureReviewV2Agent(
        context=runtime.context,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tools=[web_search_tool(runtime.context.agent_model(LiteratureReviewV2Agent.model))],
    )
    run = await agent.ainvoke({})

    return {"result": markdown_result_from_run(run), "messages": run.messages}
