"""Tying a python-docx paragraph index to a docx-editor paragraph reference.

The two libraries enumerate a document differently. The comment pass anchors an
issue to a `paragraph_index`: a position among the non-empty paragraphs of
``python-docx``'s body-level ``Document.paragraphs``. docx-editor addresses a
paragraph by a hash-anchored ref (``P7#9646``) whose number is its position
among *every* ``<w:p>`` in ``word/document.xml``, table cells and content
controls included. The indexes therefore do not line up.

They are matched by position in the file, not by text. Both libraries walk
``<w:p>`` in document order -- docx-editor over
``dom.getElementsByTagName("w:p")``, 1-based, and lxml over
``body.iter(qn("w:p"))`` -- so the k-th paragraph of one is the k-th paragraph
of the other, and each python-docx paragraph element has a document ordinal
that names its docx-editor ref directly.

Matching them by text, as this used to, breaks on a document that already
carries tracked changes: python-docx's ``paragraph.text`` leaves out the runs
inside ``w:ins`` and ``w:del``, while docx-editor reports the visible text with
insertions in it. Two paragraphs sharing wording, one of them holding an
earlier insertion, would then hand the redline to the wrong one -- and report
success. Position cannot drift that way, and it makes the old body-before-table
preference moot as well.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from docx.oxml.ns import qn
from docx_editor import ParagraphInfo
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MappedParagraph(BaseModel):
    """A python-docx paragraph, as docx-editor addresses it.

    `text` is docx-editor's visible text, insertions included, because that is
    the text a find-and-replace has to match and the text the membership check
    compares the edit's markdown line against.
    """

    ref: str
    text: str


def paragraph_ordinals(document: Any) -> Optional[Tuple[List[int], int]]:
    """``([document ordinal of each mapped paragraph], total <w:p> count)``.

    The mapped paragraphs are the non-empty body paragraphs, in the order the
    comment pass indexes them (`_inject_markers` in `paragraph_line_mapper`
    numbers exactly this list). An ordinal is 1-based over every ``<w:p>`` in
    the document, which is how docx-editor numbers its refs.

    ``None`` means a body paragraph was not found in the document's own
    ``<w:p>`` walk, which cannot happen for a file python-docx just opened --
    and if it ever did, the sequences would be out of step and nothing could be
    mapped safely.

    `document` is a python-docx ``Document``; typed loosely because
    python-docx ships no usable public type for it.
    """
    positions = {
        element: ordinal
        for ordinal, element in enumerate(document.element.body.iter(qn("w:p")), 1)
    }
    ordinals: List[int] = []
    for paragraph in document.paragraphs:
        if not paragraph.text.strip():
            continue
        ordinal = positions.get(paragraph._p)
        if ordinal is None:
            logger.warning("A body paragraph is missing from the document's own walk")
            return None
        ordinals.append(ordinal)
    return ordinals, len(positions)


def map_paragraph_refs(
    mapped_ordinals: Sequence[int],
    total_paragraphs: int,
    editor_paragraphs: Sequence[ParagraphInfo],
) -> Optional[Dict[int, MappedParagraph]]:
    """Map ``{python-docx paragraph index: docx-editor paragraph}``.

    `mapped_ordinals` and `total_paragraphs` come from `paragraph_ordinals`;
    `editor_paragraphs` is docx-editor's full listing, empty paragraphs
    included, in its own order.

    ``None`` means the two libraries do not agree on how many paragraphs the
    document has. Nothing is mapped then: with the sequences out of step, every
    ref would be off by an unknown amount, and reporting the edits as
    unplaceable beats redlining arbitrary paragraphs.
    """
    if total_paragraphs != len(editor_paragraphs):
        logger.warning(
            "Refusing to map paragraphs: python-docx sees %d and docx-editor %d",
            total_paragraphs,
            len(editor_paragraphs),
        )
        return None
    # Keyed by docx-editor's own 1-based index rather than by list position, so
    # a partial listing is caught below instead of shifting every ref.
    by_ordinal = {info.index: info for info in editor_paragraphs}
    mapped: Dict[int, MappedParagraph] = {}
    for index, ordinal in enumerate(mapped_ordinals):
        info = by_ordinal.get(ordinal)
        if info is None:
            logger.warning(
                "Refusing to map paragraphs: docx-editor has no paragraph %d",
                ordinal,
            )
            return None
        mapped[index] = MappedParagraph(ref=info.ref, text=info.text)
    return mapped
