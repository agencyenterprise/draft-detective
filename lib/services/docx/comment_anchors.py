"""Which words of the Word document each issue's comment is anchored on.

An issue with a passage gets its comment on the passage's words, so Word
highlights what the app highlights. Everything else -- no passage, or a passage
the export cannot pin down -- keeps the comment on the whole paragraph, as
before.

The passage is located in docx-editor's view of the paragraph by
`anchor_span`, the rule the redlines use, and handed to the comment pass as the
exact characters to find plus which of their repeats it is. The comment pass
then finds those characters among python-docx's runs (`comment_runs`) and falls
back to the paragraph if the two libraries do not agree on them.
"""

import asyncio
import uuid
from collections.abc import Sequence

from pydantic import BaseModel

from lib.models.issue import Issue
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.paragraph_refs import MappedParagraph
from lib.services.docx.tracked_changes.planning import paragraph_map
from lib.services.docx.tracked_changes.quote_span import anchor_span
from lib.services.text.location import all_offsets
from lib.workflows.simple_deep_agent.edit_anchoring import document_lines


class CommentAnchor(BaseModel):
    """The characters of one paragraph an issue's comment covers."""

    paragraph_index: int
    find: str
    # Which repeat of `find` in the paragraph's text, and that text as
    # docx-editor read it: the comment pass checks python-docx reads the same
    # text before trusting the index.
    occurrence: int
    paragraph_text: str


def _anchor(
    issue: Issue,
    paragraphs: dict[int, MappedParagraph],
    paragraph_line_ranges: dict[int, tuple[int, int]],
    lines: Sequence[str],
) -> CommentAnchor | None:
    passage = issue.passage
    if passage is None:
        return None
    index = find_paragraph_by_line_range(
        paragraph_line_ranges, passage.start_line, passage.start_line
    )
    paragraph = paragraphs.get(index) if index is not None else None
    if index is None or paragraph is None:
        return None
    span = anchor_span(passage, paragraph.text, paragraph_line_ranges[index], lines)
    if span is None:
        return None
    find = paragraph.text[span[0] : span[1]]
    offsets = all_offsets(paragraph.text, find)
    return CommentAnchor(
        paragraph_index=index,
        find=find,
        occurrence=len([offset for offset in offsets if offset < span[0]]),
        paragraph_text=paragraph.text,
    )


def _plan_sync(
    issues: Sequence[Issue],
    markdown: str,
    docx_path: str,
    paragraph_line_ranges: dict[int, tuple[int, int]],
    workspace_root: str | None,
) -> dict[uuid.UUID, CommentAnchor]:
    paragraphs = paragraph_map(docx_path, workspace_root)
    if paragraphs is None:
        return {}
    lines = document_lines(markdown)
    return {
        issue.id: anchor
        for issue in issues
        if (anchor := _anchor(issue, paragraphs, paragraph_line_ranges, lines))
    }


async def plan_comment_anchors(
    issues: Sequence[Issue],
    markdown: str,
    docx_path: str,
    paragraph_line_ranges: dict[int, tuple[int, int]],
    workspace_root: str | None = None,
) -> dict[uuid.UUID, CommentAnchor]:
    """``{issue id: anchor}`` for every issue whose passage can be pinned down.

    Read-only, and the document is only opened when some issue has a passage,
    so an export of issues without passages costs what it always did.
    """
    if not paragraph_line_ranges or not any(i.passage for i in issues):
        return {}
    return await asyncio.to_thread(
        _plan_sync, issues, markdown, docx_path, paragraph_line_ranges, workspace_root
    )
