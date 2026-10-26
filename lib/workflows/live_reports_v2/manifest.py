from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.bibliography_inputs import bibliography_inputs
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

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


class LiveReportsV2Manifest(SimpleDeepAgentManifest):
    """Live Reports implemented with the simple deep-agent pattern.

    Same goal as v1 (find sources published after the document's publication
    date that update or challenge its claims, and produce an addendum): the
    agent reads the document from `/main.md`, searches the web, writes the
    addendum to `/report.md` and reports each update as an issue. Its user
    prompt is the `live-reports` skill plus the document's extracted
    bibliography and publication date.
    """

    type = WorkflowRunType.LIVE_REPORTS_V2
    name = "Live Reports"
    description = "Have any of your findings been updated or contradicted by newer research? Searches the web for sources published after your document's publish date that may update or challenge your claims. Generates an addendum containing any new evidence."
    needs_web_search = True
    is_experimental = True
    required_dependencies = [
        WorkflowRunType.REFERENCE_EXTRACTION,
    ]

    skill = "live-reports"
    system_prompt = _SYSTEM_PROMPT
    progress_label = "Generate live report"
    # Web-search turns resolve every search inside one model call.
    llm_timeout = 600

    async def prompt_inputs(
        self, state: SimpleDeepAgentState, service: FileArtifactsServiceType
    ) -> str:
        return await bibliography_inputs(
            state,
            service,
            "Current bibliography from the document (already cited — do not re-list these)",
        )
