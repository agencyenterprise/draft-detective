"""Build an authoritative docx-paragraph → markdown-line-range map.

The approach avoids fuzzy matching entirely: we inject a unique sentinel at the
start of every non-empty body paragraph, run the docx through markitdown, and
read the sentinel positions out of the resulting markdown. Because the sentinels
survive the docx → HTML → markdown pipeline as inline text and do not change the
line count, the resulting line numbers are identical to those of the original
markdown that issues were indexed against.

The main conversion rasterizes charts and metafile pictures first, and each
rendered drawing occupies a markdown line, so skipping that here would shift
every line number after the first chart. Only the line matters, not the
pixels, so the same drawings are swapped for a placeholder image instead of
being rendered again with LibreOffice.
"""

import asyncio
import logging
import os
import re
import tempfile
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from lxml import etree  # type: ignore[import-untyped]

from lib.services.converters.markitdown import markitdown_converter
from lib.services.docx.drawing_rasterization import stub_docx_drawings

logger = logging.getLogger(__name__)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# No underscores or other markdown-special characters in the sentinel — markdownify
# escapes ``_`` to ``\_`` which would break regex recovery.
_MARKER_RE = re.compile(r"§§AIRP(\d+)§§")


def _marker_for(paragraph_index: int) -> str:
    """Sentinel inserted into a docx paragraph. Chosen to be regex-stable and
    markdown-inert (no characters the markdownify step escapes)."""
    return f"§§AIRP{paragraph_index}§§ "


def _inject_markers(doc: Any) -> int:
    """Prepend a unique marker run to every non-empty body paragraph.

    Returns the number of markers injected, which matches the later export code's
    notion of ``docx_paragraphs`` (i.e. ``[p for p in doc.paragraphs if
    p.text.strip()]``).
    """
    injected = 0
    for i, paragraph in enumerate(p for p in doc.paragraphs if p.text.strip()):
        element = paragraph._element
        marker_run = etree.SubElement(element, f"{{{_W_NS}}}r")
        marker_text = etree.SubElement(marker_run, f"{{{_W_NS}}}t")
        marker_text.text = _marker_for(i)
        marker_text.set(qn("xml:space"), "preserve")

        # Place the marker run immediately after <w:pPr> (or at index 0 if absent)
        # so it's the first content in the paragraph.
        pPr = element.find(qn("w:pPr"))
        element.remove(marker_run)
        if pPr is not None:
            pPr.addnext(marker_run)
        else:
            element.insert(0, marker_run)
        injected += 1
    return injected


def _extract_marker_positions(markdown: str) -> dict[int, int]:
    """Return ``{paragraph_index: 1-indexed line}`` for each marker in the markdown.

    If the same paragraph index is found multiple times (shouldn't happen in
    practice), the first occurrence wins.
    """
    positions: dict[int, int] = {}
    for line_index, line in enumerate(markdown.splitlines(), start=1):
        for match in _MARKER_RE.finditer(line):
            paragraph_index = int(match.group(1))
            positions.setdefault(paragraph_index, line_index)
    return positions


def _line_count(markdown: str) -> int:
    return markdown.count("\n") + 1


async def _convert_like_persisted(
    docx_path: str, expected_line_count: int | None
) -> str:
    """Convert the marked copy the way the persisted markdown was converted.

    Markdown stored before equations were converted one at a time lost every
    equation whenever one of them failed. When today's conversion does not
    match its line count, try that older conversion before giving up.
    """
    markdown = await markitdown_converter.convert_to_markdown(docx_path)
    if expected_line_count is None or _line_count(markdown) == expected_line_count:
        return markdown
    legacy = await markitdown_converter.convert_to_markdown(
        docx_path, keep_equations=False
    )
    if _line_count(legacy) == expected_line_count:
        return legacy
    return markdown


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


async def _marked_markdown(
    docx_path: str, expected_line_count: int | None
) -> tuple[str, int]:
    """The document's markdown with a marker on every non-empty paragraph, and
    how many markers were injected (no conversion when there are none)."""
    doc = Document(docx_path)
    injected = _inject_markers(doc)
    if injected == 0:
        return "", 0
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        doc.save(tmp_path)
        return await _convert_like_persisted(tmp_path, expected_line_count), injected
    finally:
        _remove(tmp_path)


async def build_paragraph_line_ranges(
    docx_path: str, expected_line_count: int | None = None
) -> dict[int, tuple[int, int]]:
    """Compute ``{paragraph_index: (start_line, end_line)}`` for a docx.

    ``paragraph_index`` matches the positional index of non-empty paragraphs in
    ``Document(docx_path).paragraphs`` — the same list consumed by the comment
    anchoring code.

    ``expected_line_count`` is the persisted markdown's line count. The map is
    only valid when this conversion is line-for-line the one the issues were
    indexed against. The drawings the main conversion rasterizes are stubbed
    here, which matches it whenever rasterization succeeded at ingestion; when
    it did not (LibreOffice missing, timeout), the persisted markdown has no
    lines for them, so the untouched document is converted instead. On a
    mismatch either way the map is empty — unanchorable issues are skipped and
    logged, which beats anchoring them to the wrong paragraphs.
    """
    stubbed_path = await asyncio.to_thread(stub_docx_drawings, docx_path)
    try:
        markdown_with_markers, injected = await _marked_markdown(
            stubbed_path or docx_path, expected_line_count
        )
    finally:
        if stubbed_path:
            _remove(stubbed_path)
    if injected == 0:
        return {}
    stubbed_lines = _line_count(markdown_with_markers) if stubbed_path else None
    if stubbed_lines is not None and expected_line_count not in (None, stubbed_lines):
        markdown_with_markers, injected = await _marked_markdown(
            docx_path, expected_line_count
        )

    total_lines = _line_count(markdown_with_markers)
    if expected_line_count is not None and total_lines != expected_line_count:
        logger.warning(
            "Paragraph line-range mapper: the persisted markdown has %d lines, but "
            "the conversion with drawings stubbed produced %s and the one without "
            "them %d — the conversions are structurally different; refusing to "
            "anchor",
            expected_line_count,
            stubbed_lines if stubbed_lines is not None else "n/a (no drawings)",
            total_lines,
        )
        return {}

    start_lines = _extract_marker_positions(markdown_with_markers)
    if len(start_lines) < injected:
        missing = injected - len(start_lines)
        logger.warning(
            "Paragraph line-range mapper: %d/%d markers could not be recovered "
            "from markdown (some paragraphs will be unmapped)",
            missing,
            injected,
        )

    # Derive end_line for each paragraph: the line just before the next paragraph's
    # start line. Paragraphs that share a line (table cells) get (start, start).
    sorted_by_line = sorted(start_lines.items(), key=lambda kv: (kv[1], kv[0]))
    ranges: dict[int, tuple[int, int]] = {}
    for i, (para_index, start_line) in enumerate(sorted_by_line):
        if i + 1 < len(sorted_by_line):
            next_start = sorted_by_line[i + 1][1]
            end_line = max(start_line, next_start - 1)
        else:
            end_line = total_lines
        ranges[para_index] = (start_line, end_line)
    return ranges


def find_paragraph_by_line_range(
    paragraph_line_ranges: dict[int, tuple[int, int]],
    start_line: int,
    end_line: int,
) -> int | None:
    """Return the paragraph whose line range overlaps ``(start_line, end_line)``.

    Ties are broken by choosing the paragraph with the lowest index for
    determinism when multiple paragraphs overlap equally (e.g. table cells that
    share a markdown line).
    """
    best: int | None = None
    for para_index, (para_start, para_end) in paragraph_line_ranges.items():
        if para_start <= end_line and para_end >= start_line:
            if best is None or para_index < best:
                best = para_index
    return best
