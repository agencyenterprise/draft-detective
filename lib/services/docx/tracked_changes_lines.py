"""What a markdown line says about the Word paragraph it maps to.

An edit is anchored to one line of the converted markdown, and the export has
to decide whether that line really is the mapped paragraph's own before any of
its words are redlined. Deciding needs the line in the form the paragraph
carries, which is the rendered one, so the rendering lives here too.
"""

import re
from difflib import SequenceMatcher
from typing import Optional, Sequence

from lib.models.issue_edit import IssueEdit
from lib.services.markdown_text import render_line_text
from lib.workflows.simple_deep_agent.edit_anchoring import normalize_whitespace

# A footnote reference as the markdown carries it, before any syntax is
# stripped: MarkItDown writes a DOCX footnote as a link into the footnotes
# section (`[[1]](#footnote-2)`), and a converter emitting reference-style
# markdown writes `[^1]`. Word carries the reference as a mark, so the
# paragraph's text has no characters for it while the markdown line does.
#
# Matched on the raw line on purpose. A bare `[1]` is left alone: in prose it
# is a visible citation the Word paragraph carries too, and dropping it would
# make a line and its own paragraph look like different passages.
_FOOTNOTE_REFERENCE = re.compile(r"\[\[\d+\]\]\(#footnote-[^)]*\)|\[\^\d+\]")

# How alike a line and a paragraph must be to be the same passage, and how
# long both have to be before likeness is worth measuring at all.
_MIN_SIMILARITY = 0.9
_MIN_COMPARABLE_LENGTH = 20


def source_line(edit: IssueEdit, document_lines: Sequence[str]) -> Optional[str]:
    """The markdown line the edit was anchored to, if the document still has it."""
    if edit.start_line < 1 or edit.start_line > len(document_lines):
        return None
    return document_lines[edit.start_line - 1]


def _without_footnote_references(line: str) -> str:
    """The markdown line with its footnote reference markers dropped.

    Word shows a footnote as a reference mark rather than as text, so the
    markers are the one thing a markdown line carries that its own paragraph
    never will. Everything else the line says is compared as written.
    """
    return _FOOTNOTE_REFERENCE.sub("", line)


def line_belongs_to_paragraph(line: Optional[str], paragraph_text: str) -> bool:
    """Whether the edit's own markdown line is part of the mapped paragraph.

    A paragraph's line range runs to the line before the next body paragraph
    starts, so a table's markdown rows fall inside the range of the paragraph
    above them. Mapping by range alone would hand a table-cell edit to that
    paragraph, and a quote the paragraph happens to carry as well would then be
    redlined on the wrong words. Comparing the whole line against the
    paragraph's text settles it:

    1. The line loses its footnote reference markers, which Word carries as
       marks rather than as text, and is then rendered the way the reader sees
       it. A bare `[1]` survives: a bracketed number in prose is a citation
       the paragraph shows as well.
    2. The same text either way round is the same passage, whatever its
       length.
    3. Either text *containing* the other is the same passage too, since a
       Word paragraph holding hard line breaks converts to several markdown
       lines and the line can be the shorter of the two -- but only once the
       shorter of them is at least `_MIN_COMPARABLE_LENGTH` characters. A
       short nested line is contained by accident: a list item or a table cell
       rendering to just ``14%`` sits inside any paragraph that quotes a
       percentage, and letting it in would redline the prose above it instead
       of the cell.
    4. Otherwise they are the same passage when they are `_MIN_SIMILARITY`
       alike over their whole length, which covers conversion drift anywhere
       in a long paragraph -- an inline image, a bookmark, a field result, a
       trailing clause MarkItDown writes and Word does not show. Measuring the
       whole text rather than a shared opening is what keeps a nested block or
       a content control that merely repeats the paragraph's first words out:
       boilerplate at the front no longer buys it the paragraph.

    The length floor on the last two rules is the same one, and it is already
    more than a table row (``| Metric | Value |``) can share with prose.
    Nothing else is the mapped paragraph's own line.
    """
    if line is None:
        return False
    line_text = _rendered_line(line)
    para_text = normalize_whitespace(paragraph_text)
    if not line_text or not para_text:
        return False
    if line_text == para_text:
        return True
    if min(len(line_text), len(para_text)) < _MIN_COMPARABLE_LENGTH:
        return False
    if line_text in para_text or para_text in line_text:
        return True
    similarity = SequenceMatcher(None, line_text, para_text).ratio()
    return similarity >= _MIN_SIMILARITY


def _rendered_line(line: str) -> str:
    """One markdown line as the Word paragraph would carry it.

    The same treatment the membership check gives a line: footnote reference
    markers off, since Word shows those as marks rather than as text, then
    rendered and whitespace-normalized.
    """
    return normalize_whitespace(render_line_text(_without_footnote_references(line)))
