"""Manifest for the Reviewer Response Memos workflow.

Runs the `review-assistant` skill to produce one response memo per reviewer:
each reviewer point echoed verbatim with the author's reply stating how the
revision addressed it (or why it was not changed).

This is the second of the three `review-assistant` outputs. It compares two
revisions of the main document, both available in the mounted file tree:

- the **original draft** = the main document of the *reviewed revision* (the
  latest revision under `/revisions/` with reviewer memos), and
- the **revised draft** = the current revision's main document at `/main.md`.

The revised draft is supplied through the ordinary revision flow ("Replace main
document"); there is no separate upload for it.
"""

from typing import TYPE_CHECKING, Optional

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import HtmlReportDeepAgentManifest

if TYPE_CHECKING:
    from lib.services.file_artifacts_service.file_artifacts_service_type import (
        FileArtifactsServiceType,
    )

_INTRO = """\
You are running the review-assistant skill to produce reviewer response memos. \
Read the skill instructions at `/skills/review-assistant/SKILL.md` and the \
companion tone skill at `/skills/voice-and-tone/SKILL.md` and follow them \
exactly.

"""

# Where the inputs are found when the run reads the project tree.
_PROJECT_INPUTS = """\
## Inputs

The project's revisions are mounted under `/revisions/<n>/`. Find the \
**reviewed revision**: the highest-numbered revision folder that contains a \
`reviewer-memos/` directory. Ignore reviewer memos in any earlier revision.

- The original draft (the version the reviewers reviewed) is \
`/revisions/<reviewed>/main.md`.
- The revised draft (the current version that addresses the comments) is \
`/main.md`.
- The reviewer memos are the files under \
`/revisions/<reviewed>/reviewer-memos/`. Read every memo in full.

"""

# Where they are when the run was handed its inputs (config.input_files).
_EXPLICIT_INPUTS = """\
## Inputs

The files picked for this run are mounted under `/inputs/`, one folder per \
input. Read only these: nothing else from the project is part of this run.

- The original draft (the version the reviewers reviewed) is the file under \
`/inputs/reviewed-draft/`.
- The revised draft (the version that addresses the comments) is the file \
under `/inputs/revised-draft/`.
- The reviewer memos are the files under `/inputs/reviewer-memos/`. Read \
every memo in full.

"""

_TASK_AND_OUTPUT = """\
## Task

Produce ONLY the "Reviewer response memos" output described in the skill, not \
the revision-planning summary and not the coverage report. Follow the skill's \
specification for it exactly: everything about the memos' content, structure, \
and formatting is defined there.

## Output

Write the memos, all of them together, to `/report.html` using the \
`write_file` tool, as a single, complete, self-contained HTML document with \
its own inline `<style>` \
block implementing the skill's formatting conventions. Self-contained means no \
external stylesheets, fonts, scripts, or images, and no `<script>` of any \
kind; embed any images as `data:` URIs.

`/report.html` is the deliverable: it is read from the filesystem when you \
finish, and nothing you say in your final message is used in its place. Write \
the whole document, and if you revise it, write it again in full.\
"""

_SYSTEM_PROMPT = _INTRO + _PROJECT_INPUTS + _TASK_AND_OUTPUT
_EXPLICIT_INPUTS_SYSTEM_PROMPT = _INTRO + _EXPLICIT_INPUTS + _TASK_AND_OUTPUT


class ReviewerResponseMemosManifest(HtmlReportDeepAgentManifest):
    """Generates one reviewer response memo per reviewer, comparing revisions."""

    type = WorkflowRunType.REVIEWER_RESPONSE_MEMOS
    name = "Reviewer Response Memos"
    description = (
        "Drafts one response memo per reviewer, comparing the revised draft (the "
        "current main document) against the reviewed draft. Each reviewer point "
        "is echoed verbatim with a reply on how the revision addressed it. "
        "Requires reviewer memos and a revised draft (replace the main document "
        "after uploading the memos)."
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
        # reviewed revision's main, otherwise there is nothing to compare.
        current_main = await service.get_main_file()
        original_main = await service.get_main_file(revision=reviewed_revision)
        if current_main.file_id == original_main.file_id:
            return (
                "The reviewed revision is still the current main document. "
                "Replace the main document with your revised draft, then re-run "
                "this assessment to generate response memos."
            )
        return None
