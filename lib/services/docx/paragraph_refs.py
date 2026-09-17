"""Tying a python-docx paragraph index to a docx-editor paragraph reference.

The two libraries enumerate a document differently. The comment pass anchors an
issue to a `paragraph_index`: a position among the non-empty paragraphs of
``python-docx``'s body-level ``Document.paragraphs``. docx-editor walks every
``<w:p>`` in ``word/document.xml``, table cells included, and addresses each by
a hash-anchored ref (``P7#9646``). The indexes therefore do not line up, and
assuming they do would redline a paragraph nobody asked about.

So the two are matched by text: for the target python-docx paragraph, take the
docx-editor paragraphs whose text is identical, and pick the one at the same
ordinal the target holds among the python-docx paragraphs carrying that text. A
paragraph whose text appears nowhere on the other side stays unmapped, and its
edits are reported as unplaceable rather than guessed at.

Paragraphs inside table cells are considered last. python-docx never lists
them, so a cell repeating a body paragraph's wording would otherwise claim that
paragraph's ordinal and the redline would land in the table.
"""

import logging
from typing import Collection, Dict, List, Mapping, Sequence

from docx_editor import ParagraphInfo
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MappedParagraph(BaseModel):
    """A python-docx paragraph, as docx-editor addresses it."""

    ref: str
    text: str


def _by_text(
    editor_paragraphs: Sequence[ParagraphInfo],
) -> Mapping[str, List[ParagraphInfo]]:
    grouped: Dict[str, List[ParagraphInfo]] = {}
    for info in editor_paragraphs:
        grouped.setdefault(info.text, []).append(info)
    return grouped


def map_paragraph_refs(
    docx_paragraph_texts: Sequence[str],
    editor_paragraphs: Sequence[ParagraphInfo],
    in_table_refs: Collection[str] = (),
) -> Dict[int, MappedParagraph]:
    """Map ``{python-docx paragraph index: docx-editor paragraph}``.

    `docx_paragraph_texts` is the text of each non-empty paragraph of
    ``Document.paragraphs``, in order -- the same list the comment pass indexes
    into. `in_table_refs` are the refs docx-editor reports as sitting in a
    table cell; they are only used when nothing in the body matches.
    Unmapped indexes are simply absent from the result.
    """
    grouped = _by_text(editor_paragraphs)
    seen: Dict[str, int] = {}
    mapped: Dict[int, MappedParagraph] = {}
    for index, text in enumerate(docx_paragraph_texts):
        ordinal = seen.get(text, 0)
        seen[text] = ordinal + 1
        all_matches = grouped.get(text, [])
        body_matches = [info for info in all_matches if info.ref not in in_table_refs]
        matches = body_matches or all_matches
        if ordinal >= len(matches):
            logger.debug(
                "Paragraph %d has no docx-editor counterpart (%d/%d matches for its text)",
                index,
                len(matches),
                ordinal + 1,
            )
            continue
        match = matches[ordinal]
        mapped[index] = MappedParagraph(ref=match.ref, text=match.text)
    return mapped
