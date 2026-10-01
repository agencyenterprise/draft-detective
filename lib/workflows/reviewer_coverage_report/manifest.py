"""Manifest for the Reviewer Coverage Report workflow.

Runs the `review-assistant` skill to produce the QA-manager-facing coverage
report: a single consolidated view of every reviewer point, its verdict, and an
overall read on how responsive the revision was.

This is the third and final `review-assistant` output. Like the response memos,
it compares two revisions of the main document from the mounted file tree:

- the **original draft** = the main document of the *reviewed revision* (the
  latest revision under `/revisions/` with reviewer memos), and
- the **revised draft** = the current revision's main document at `/main.md`.

Coverage is assessed from the draft diff (an objective read for the QAM). When
the author has uploaded their final response memos to the current revision, they
are mounted under `/revisions/<current>/response-memos/` and read too, so each
verdict can check what the author told the reviewer against the draft. They are
optional: without them the report runs on the draft diff alone.
"""

from typing import TYPE_CHECKING, Optional

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import HtmlReportDeepAgentManifest

if TYPE_CHECKING:
    from lib.services.file_artifacts_service.file_artifacts_service_type import (
        FileArtifactsServiceType,
    )

_INTRO = """\
You are running the review-assistant skill to produce a reviewer coverage \
report for a QA manager. Read the skill instructions at \
`/skills/review-assistant/SKILL.md` and the companion tone skill at \
`/skills/voice-and-tone/SKILL.md` and follow them exactly.

"""

# Where the inputs are found when the run reads the project tree.
_PROJECT_INPUTS = """\
## Inputs

The project's revisions are mounted under `/revisions/<n>/`. Find the \
**reviewed revision**: the highest-numbered revision folder that contains a \
`reviewer-memos/` directory. Ignore reviewer memos in any earlier revision.

- The original draft (the version the reviewers reviewed) is \
`/revisions/<reviewed>/main.md`.
- The revised draft (the current version) is `/main.md`.
- The reviewer memos are the files under \
`/revisions/<reviewed>/reviewer-memos/`. Read every memo in full.
- The author's response memos, if they uploaded any, are the files under \
`/revisions/<current>/response-memos/`, where `<current>` is the \
highest-numbered revision folder. Read every one in full. Ignore response \
memos in any other revision: they describe a draft that has since been \
replaced.

"""

# Where they are when the run was handed its inputs (config.input_files).
_EXPLICIT_INPUTS = """\
## Inputs

The files picked for this run are mounted under `/inputs/`, one folder per \
input. Read only these: nothing else from the project is part of this run.

- The original draft (the version the reviewers reviewed) is the file under \
`/inputs/reviewed-draft/`.
- The revised draft is the file under `/inputs/revised-draft/`.
- The reviewer memos are the files under `/inputs/reviewer-memos/`. Read \
every memo in full.
- The author's response memos, if any were picked, are the files under \
`/inputs/response-memos/`. Read every one in full.

"""

_TASK_AND_OUTPUT = """\
Assess coverage by comparing the revised draft against the original. When \
response memos are present, use them as the skill describes for the coverage \
report, but the revised draft remains the evidence: a response is a claim to \
verify, not a verdict to copy. When there are none, assess from the draft \
comparison alone and say so in the report's header.

## Task

Produce ONLY the "Reviewer coverage report" output described in the skill, \
not the revision-planning summary and not the reviewer response memos. Follow \
the skill's specification for it exactly: everything about the report's \
content, structure, and formatting is defined there.

## Output

Write the report to `/report.html` using the `write_file` tool, as a \
single, complete, self-contained HTML document with its own inline `<style>` \
block implementing the skill's formatting conventions. Self-contained means no \
external stylesheets, fonts, scripts, or images, and no `<script>` of any \
kind; embed any images as `data:` URIs.

`/report.html` is the deliverable: it is read from the filesystem when you \
finish, and nothing you say in your final message is used in its place. Write \
the whole document, and if you revise it, write it again in full.\
"""

_SYSTEM_PROMPT = _INTRO + _PROJECT_INPUTS + _TASK_AND_OUTPUT
_EXPLICIT_INPUTS_SYSTEM_PROMPT = _INTRO + _EXPLICIT_INPUTS + _TASK_AND_OUTPUT


class ReviewerCoverageReportManifest(HtmlReportDeepAgentManifest):
    """Generates a consolidated reviewer coverage report for a QA manager."""

    type = WorkflowRunType.REVIEWER_COVERAGE_REPORT
    name = "Reviewer Coverage Report"
    description = (
        "Consolidates every reviewer's points into a single QA-manager view: a "
        "verdict per point (addressed, partially addressed, declined with "
        "rationale, or not addressed), a summary count table, and an overall "
        "responsiveness read. Requires reviewer memos and a revised draft "
        "(replace the main document after uploading the memos). Reads the "
        "author's response memos too, when they are uploaded to the revised draft."
    )
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = True
    # Started only from the Peer Review tab, which sequences the prerequisites.
    # Creating a revision must not fire these off on its own.
    auto_rerun_on_new_revision = False

    skill = "review-assistant"
    system_prompt = _SYSTEM_PROMPT
    explicit_inputs_system_prompt = _EXPLICIT_INPUTS_SYSTEM_PROMPT
    reasoning_effort = "high"

    async def precheck(self, service: "FileArtifactsServiceType") -> Optional[str]:
        reviewed_revision = await service.get_latest_reviewer_memo_revision()
        if reviewed_revision is None:
            return (
                "No reviewer memos were found for this project. Upload one or "
                "more reviewer memos, then re-run this assessment."
            )
        # The revised draft is the current main; it must differ from the
        # reviewed revision's main, otherwise there is nothing to assess.
        current_main = await service.get_main_file()
        original_main = await service.get_main_file(revision=reviewed_revision)
        if current_main.file_id == original_main.file_id:
            return (
                "The reviewed revision is still the current main document. "
                "Replace the main document with your revised draft, then re-run "
                "this assessment to generate a coverage report."
            )
        return None
