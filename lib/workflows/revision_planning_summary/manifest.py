"""Manifest for the Revision-Planning Summary workflow.

Runs the `review-assistant` skill against the reviewed draft plus the uploaded
reviewer memos to produce a revision-planning summary: the reviewer memos
reproduced verbatim, each point labeled with a stable ID, and a compact planning
note under each point (where it lives in the draft, its scope, and a short
suggestion for addressing it).

This is the first of the three `review-assistant` outputs. The skill body
(`skills/review-assistant/SKILL.md`) is the single source of truth for how the
summary is produced; it is loaded as the agent's user prompt and is also mounted
read-only into the agent filesystem alongside the `voice-and-tone` skill.

It operates on the *reviewed revision*: the latest revision under `/revisions/`
that has reviewer memos attached. The agent finds it from the mounted file tree.
"""

from typing import TYPE_CHECKING, Optional

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import HtmlReportDeepAgentManifest

if TYPE_CHECKING:
    from lib.services.file_artifacts_service.file_artifacts_service_type import (
        FileArtifactsServiceType,
    )

_INTRO = """\
You are running the review-assistant skill to produce a revision-planning \
summary. Read the skill instructions at `/skills/review-assistant/SKILL.md` and \
the companion tone skill at `/skills/voice-and-tone/SKILL.md` and follow them \
exactly.

"""

# Where the inputs are found when the run reads the project tree.
_PROJECT_INPUTS = """\
## Inputs

The project's revisions are mounted under `/revisions/<n>/`. Find the \
**reviewed revision**: the highest-numbered revision folder that contains a \
`reviewer-memos/` directory. Ignore reviewer memos in any earlier revision.

- The draft under review is that revision's main document, \
`/revisions/<reviewed>/main.md`.
- The reviewer memos are the files under \
`/revisions/<reviewed>/reviewer-memos/`. Read every memo in full.

"""

# Where they are when the run was handed its inputs (config.input_files).
_EXPLICIT_INPUTS = """\
## Inputs

The files picked for this run are mounted under `/inputs/`, one folder per \
input. Read only these: nothing else from the project is part of this run.

- The draft under review is the file under `/inputs/reviewed-draft/`.
- The reviewer memos are the files under `/inputs/reviewer-memos/`. Read \
every memo in full.

"""

_TASK_AND_OUTPUT = """\
## Task

Produce ONLY the "Revision-planning summary" output described in the skill, \
not the reviewer response memos and not the coverage report. Follow the \
skill's specification for it exactly: everything about the summary's content, \
structure, and formatting is defined there.

## Output

Write the summary to `/report.html` using the `write_file` tool, as a \
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


class RevisionPlanningSummaryManifest(HtmlReportDeepAgentManifest):
    """Generates a revision-planning summary from reviewer memos."""

    type = WorkflowRunType.REVISION_PLANNING_SUMMARY
    name = "Revision-Planning Summary"
    description = (
        "Builds a revision-planning summary from reviewer notes/memos and the current "
        "draft. Produces a report that breaks every reviewer's points down into "
        "discrete, actionable suggestions and maps each to the part of the draft "
        "it corresponds to. Requires one or more reviewer memos."
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
        if await service.get_latest_reviewer_memo_revision() is None:
            return (
                "No reviewer memos were found for this project. Upload one or "
                "more reviewer memos, then re-run this assessment."
            )
        return None
