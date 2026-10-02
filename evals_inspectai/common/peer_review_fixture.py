"""Project setup for the peer-review (`review-assistant`) e2e evals.

The three `review-assistant` workflows (revision-planning summary, reviewer
response memos, reviewer coverage report) need more project state than the
other e2e evals: alongside the draft they need one or more files with the
`reviewer_memo` role, attached to the revision the reviewers reviewed. Those
uploads have to follow the draft rather than accompany it, so the project is
set up first and the memos go up afterwards.

The sequence is:

1. create the project with the reviewed draft as its main document, running
   only `document_processing`;
2. wait for that to finish, so memo uploads do not race the conversion of the
   main document;
3. upload each reviewer memo with `role=reviewer_memo` against revision 1;
4. optionally, for the workflows that compare two drafts, create revision 2,
   upload the revised draft as its main document, and run `document_processing`
   again;
5. optionally, upload the author's response memos with `role=response_memo`
   against revision 2, the revised draft they describe, as the Peer Review tab
   does;
6. start the target workflow and wait for it.

The order of 3 and 4 is not interchangeable. Creating a revision cancels any
workflow still running against the outgoing one, so the memos have to be in
place first; they also need to stay attached to revision 1, which is what the
workflows treat as the reviewed draft.

The last step is separate from the first on purpose: the workflows short-circuit
through their `precheck` when the state they need is missing, so the target
workflow must not be started until the fixture is complete.
"""

import logging
from typing import Any, NamedTuple

from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    create_revision,
    poll_until_complete,
    start_workflow_types,
    tus_upload_file,
)

logger = logging.getLogger(__name__)

_DOCUMENT_PROCESSING = "document_processing"
_REVIEWER_MEMO_ROLE = "reviewer_memo"
_RESPONSE_MEMO_ROLE = "response_memo"
_MAIN_ROLE = "main"

# The reviewed revision. The memos always describe the first draft, so they
# attach to revision 1 whether or not a revised draft follows in revision 2.
REVIEWED_REVISION = 1

DOCUMENT_PROCESSING_TIMEOUT_S = 900


class ReviewerMemo(NamedTuple):
    """One reviewer memo to attach to the reviewed revision."""

    file_name: str
    content: str


class ResponseMemo(NamedTuple):
    """One author response memo to attach to the revised draft."""

    file_name: str
    content: str


async def setup_peer_review_project(
    draft: str,
    memos: list[ReviewerMemo],
    revised_draft: str | None = None,
    response_memos: list[ResponseMemo] | None = None,
    draft_file_name: str = "eval-draft.md",
    revised_draft_file_name: str = "eval-draft-revised.md",
    document_processing_timeout_s: float = DOCUMENT_PROCESSING_TIMEOUT_S,
) -> str:
    """Create a project holding a reviewed draft plus its reviewer memos.

    Args:
        draft: Markdown of the draft the reviewers reviewed.
        memos: Reviewer memos, in the order the reviewers should be lettered
            (the first is reviewer A, the second B, and so on).
        revised_draft: Markdown of the draft that answers the memos. When given,
            it lands as the main document of a second revision, which is what
            the workflows that compare two drafts require. Must differ from
            `draft`: identical content is deduplicated to the same file, which
            leaves those workflows with nothing to compare and short-circuits
            their precheck.
        response_memos: The author's replies to the reviewers. Uploaded to
            the revised draft's revision, so they need `revised_draft`.
        draft_file_name: Display name for the reviewed main document.
        revised_draft_file_name: Display name for the revised main document.
        document_processing_timeout_s: How long to wait for each
            `document_processing` run.

    Returns:
        The project_id, fully set up, with no analysis workflow started.
    """
    if not memos:
        raise ValueError("A peer-review project needs at least one reviewer memo")
    if response_memos and revised_draft is None:
        raise ValueError(
            "response_memos describe a revised draft; pass revised_draft as well"
        )
    if revised_draft is not None and revised_draft == draft:
        raise ValueError(
            "revised_draft is identical to draft; it would be deduplicated to "
            "the same file and the comparing workflows would have nothing to do"
        )

    project_id = await create_project_and_start_workflows(
        file_content=draft,
        file_name=draft_file_name,
        workflow_types=[_DOCUMENT_PROCESSING],
    )

    await poll_until_complete(
        project_id=project_id,
        workflow_type=_DOCUMENT_PROCESSING,
        timeout_s=document_processing_timeout_s,
    )

    for memo in memos:
        await tus_upload_file(
            project_id=project_id,
            file_name=memo.file_name,
            content=memo.content,
            role=_REVIEWER_MEMO_ROLE,
            revision=REVIEWED_REVISION,
        )

    if revised_draft is not None:
        revised_revision = await _add_revised_draft(
            project_id=project_id,
            revised_draft=revised_draft,
            file_name=revised_draft_file_name,
            document_processing_timeout_s=document_processing_timeout_s,
        )
        # Sent with an explicit revision, as the app does, so the upload is
        # rejected rather than misfiled if the revision moved underneath it.
        for response in response_memos or []:
            await tus_upload_file(
                project_id=project_id,
                file_name=response.file_name,
                content=response.content,
                role=_RESPONSE_MEMO_ROLE,
                revision=revised_revision,
            )

    logger.info(
        "Peer-review project %s ready with %d reviewer memo(s)%s%s",
        project_id,
        len(memos),
        " and a revised draft" if revised_draft is not None else "",
        f" and {len(response_memos)} response memo(s)" if response_memos else "",
    )
    return project_id


async def _add_revised_draft(
    project_id: str,
    revised_draft: str,
    file_name: str,
    document_processing_timeout_s: float,
) -> int:
    """Put the revised draft in a second revision, process it, and return it.

    The main document is uploaded without an explicit revision: a main document
    defines the revision it lands in, and the upload endpoint rejects an attempt
    to back-date one. `document_processing` is then run and awaited for the new
    revision rather than left to the target workflow's dependency resolution,
    so a conversion failure is reported as itself instead of surfacing later as
    a stalled dependency.
    """
    revision = await create_revision(project_id)

    await tus_upload_file(
        project_id=project_id,
        file_name=file_name,
        content=revised_draft,
        role=_MAIN_ROLE,
    )

    await start_workflow_types(project_id, [_DOCUMENT_PROCESSING])
    await poll_until_complete(
        project_id=project_id,
        workflow_type=_DOCUMENT_PROCESSING,
        timeout_s=document_processing_timeout_s,
    )
    logger.info("Revised draft in place as revision %s", revision)
    return revision


async def run_review_assistant_workflow(
    project_id: str,
    workflow_type: str,
    timeout_s: float,
    poll_interval_s: float = 5,
) -> dict[str, Any]:
    """Start one review-assistant workflow on a prepared project and await it.

    Returns the completed run's WorkflowRunDetail dict.
    """
    await start_workflow_types(project_id, [workflow_type])
    return await poll_until_complete(
        project_id=project_id,
        workflow_type=workflow_type,
        timeout_s=timeout_s,
        interval_s=poll_interval_s,
    )
