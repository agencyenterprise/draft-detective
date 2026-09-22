"""Writing the planned redlines into a DOCX, as Word tracked changes.

The comment pass tells an author what is wrong; this pass offers the fix as a
``w:del`` + ``w:ins`` pair, so the author can accept or reject each proposed
edit where they are already reading the document.

Ordering is not a preference. python-docx paragraph text stops carrying
inserted and deleted runs once tracked changes exist, so the paragraph index
map the comment pass anchors to is only valid before this pass runs: comments
first, save, then redlines.

The instructions come from `lib.services.docx.tracked_changes_planning`, which
resolved every one of them against the original file. A caller writes twice --
once to a throwaway copy, whose outcomes settle what the comments may claim,
and once for real; see `lib.services.docx.edit_export`.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Sequence

from docx_editor import BatchOperationError, Document as EditorDocument, EditOperation

from lib.services.docx.tracked_changes_models import (
    TRACKED_CHANGE_AUTHOR,
    EditOutcome,
    PlannedEdit,
    editor_workspace,
)

logger = logging.getLogger(__name__)


def _apply_paragraph(
    doc: EditorDocument, ref: str, edits: List[PlannedEdit]
) -> List[EditOutcome]:
    """Write one paragraph's redlines in a single atomic batch.

    Back-to-front: docx-editor matches each operation against the paragraph as
    it stands, so doing the later spans first leaves the earlier ones' offsets
    and occurrence counts untouched.
    """
    ordered = sorted(edits, key=lambda edit: edit.span, reverse=True)
    try:
        results = doc.batch_edit(
            [
                EditOperation.replace(
                    edit.find,
                    edit.replace_with,
                    paragraph=ref,
                    occurrence=edit.occurrence,
                )
                for edit in ordered
            ]
        )
    # ValueError as well as BatchOperationError: docx-editor validates an
    # operation's own arguments when it is built, and one paragraph's rejection
    # must not cost the rest of the document its redlines.
    except (BatchOperationError, ValueError) as error:
        reason = error.reason if isinstance(error, BatchOperationError) else str(error)
        logger.warning(
            "Tracked changes for paragraph %s were rejected: %s", ref, reason
        )
        return [
            EditOutcome(edit_id=edit.edit_id, status="failed", detail=reason)
            for edit in ordered
        ]
    outcomes: List[EditOutcome] = []
    for edit, result in zip(ordered, results):
        # No revision group means docx-editor wrote nothing -- the operation
        # was a no-op, or it spliced into text an earlier one inserted. Either
        # way there is no redline for the author to accept, so the edit did not
        # apply however quietly the call returned.
        if result.group_id is None:
            logger.warning(
                "Tracked change for edit %s in paragraph %s created no revision "
                "group -- it may have spliced into an earlier insertion",
                edit.edit_id,
                ref,
            )
            outcomes.append(
                EditOutcome(
                    edit_id=edit.edit_id,
                    status="failed",
                    detail="the change produced no tracked revision in Word",
                )
            )
            continue
        outcomes.append(EditOutcome(edit_id=edit.edit_id, status="applied"))
    return outcomes


def _apply_sync(
    docx_path: str,
    planned: Sequence[PlannedEdit],
    author: str,
    workspace_root: Optional[str],
) -> List[EditOutcome]:
    by_paragraph: Dict[str, List[PlannedEdit]] = {}
    for edit in planned:
        by_paragraph.setdefault(edit.paragraph_ref, []).append(edit)

    outcomes: List[EditOutcome] = []
    with editor_workspace(workspace_root) as workspace:
        doc = EditorDocument.open(docx_path, author=author, workspace_dir=workspace)
        try:
            for ref in sorted(by_paragraph):
                outcomes.extend(_apply_paragraph(doc, ref, by_paragraph[ref]))
            doc.save()
        finally:
            doc.close()
    return outcomes


async def apply_tracked_changes(
    docx_path: str,
    planned: Sequence[PlannedEdit],
    author: str = TRACKED_CHANGE_AUTHOR,
    workspace_root: Optional[str] = None,
) -> List[EditOutcome]:
    """Write the planned redlines into `docx_path`, in place.

    The refs a plan carries were computed on the original file and stay valid
    here: they are anchored to a hash of the paragraph's visible text, which
    adding Word comments does not change. A paragraph whose batch is rejected
    leaves the rest of the document redlined -- each paragraph is its own
    batch, and its edits come back as ``failed``.
    """
    if not planned:
        return []
    return await asyncio.to_thread(
        _apply_sync, docx_path, planned, author, workspace_root
    )
