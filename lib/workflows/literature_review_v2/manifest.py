from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.bibliography_inputs import bibliography_inputs
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

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


class LiteratureReviewV2Manifest(SimpleDeepAgentManifest):
    """Literature review implemented with the simple deep-agent pattern.

    Same goal as v1 (surface relevant academic sources the document may have
    missed, both supporting and conflicting): the agent reads the document from
    `/main.md`, searches the web, writes its markdown report to `/report.md` and
    reports each recommended source as an issue. Its user prompt is the
    `literature-review` skill plus the document's extracted bibliography and
    publication date.
    """

    type = WorkflowRunType.LITERATURE_REVIEW_V2
    name = "Literature Review"
    description = "Are there relevant sources you may have missed? Searches the web for academic sources related to your document's claims, surfacing both supporting and conflicting papers that have not already been cited."
    needs_web_search = True
    is_experimental = True
    required_dependencies = [
        WorkflowRunType.REFERENCE_EXTRACTION,
    ]

    skill = "literature-review"
    system_prompt = _SYSTEM_PROMPT
    progress_label = "Review literature"
    # Web-search turns resolve every search inside one model call.
    llm_timeout = 600

    async def prompt_inputs(
        self, state: SimpleDeepAgentState, service: FileArtifactsServiceType
    ) -> str:
        return await bibliography_inputs(
            state,
            service,
            "Extracted bibliography",
        )
