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


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _save_marked_copy(docx_path: str, marked_path: str) -> int:
    """Save `docx_path` with a marker on every non-empty paragraph; return
    how many were injected."""
    doc = Document(docx_path)
    injected = _inject_markers(doc)
    doc.save(marked_path)
    return injected


async def _conversion_matching(
    marked: list[str], expected_line_count: int
) -> tuple[str | None, list[int]]:
    """The marked conversion the persisted markdown was made with, and the
    line counts of every conversion tried.

    `marked` is the marked copy with drawings stubbed, then (when there were
    drawings) the untouched one. Each is tried with equations converted one at
    a time and then the older way, which lost every equation whenever one
    failed. Stubbing and keeping equations only ever add lines, so the first
    candidate is the longest: when it matches, nothing else can match with
    different paragraph positions, and it is taken at once. A later match is
    checked against the remaining candidates, since stubbed charts without
    equations can tie with equations without charts: when two conversions
    match the count but place paragraphs differently, neither can be trusted
    and the result is None.
    """
    counts: list[int] = []
    match: str | None = None
    for keep_equations in (True, False):
        for path in marked:
            markdown = await markitdown_converter.convert_to_markdown(
                path, keep_equations=keep_equations
            )
            counts.append(_line_count(markdown))
            if counts[-1] != expected_line_count:
                continue
            if match is None:
                if len(counts) == 1:
                    return markdown, counts
                match = markdown
            elif _extract_marker_positions(markdown) != _extract_marker_positions(
                match
            ):
                logger.warning(
                    "Paragraph line-range mapper: two conversions match the "
                    "persisted markdown's %d lines but place paragraphs "
                    "differently; refusing to anchor",
                    expected_line_count,
                )
                return None, counts
    return match, counts


async def _marked_markdown(
    docx_path: str, expected_line_count: int | None
) -> tuple[str | None, int]:
    """The markdown with paragraph markers that matches the persisted one, and
    how many markers were injected. None when no conversion can be trusted."""
    stubbed_path = await asyncio.to_thread(stub_docx_drawings, docx_path)
    sources = [path for path in (stubbed_path, docx_path) if path]
    with tempfile.TemporaryDirectory(prefix="line-mapper-") as workdir:
        try:
            marked = [
                os.path.join(workdir, f"marked-{i}.docx") for i in range(len(sources))
            ]
            injected = 0
            for source, target in zip(sources, marked):
                injected = await asyncio.to_thread(_save_marked_copy, source, target)
        finally:
            if stubbed_path:
                _remove(stubbed_path)
        if injected == 0:
            return "", 0
        if expected_line_count is None:
            return await markitdown_converter.convert_to_markdown(marked[0]), injected
        markdown, counts = await _conversion_matching(marked, expected_line_count)
    if markdown is None:
        logger.warning(
            "Paragraph line-range mapper: the persisted markdown has %d lines; "
            "the conversions tried produced %s — refusing to anchor",
            expected_line_count,
            counts,
        )
    return markdown, injected


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
    lines for them, so the untouched document is converted instead. When no
    conversion matches, or two match ambiguously, the map is empty —
    unanchorable issues are skipped and logged, which beats anchoring them to
    the wrong paragraphs.
    """
    markdown_with_markers, injected = await _marked_markdown(
        docx_path, expected_line_count
    )
    if markdown_with_markers is None or injected == 0:
        return {}
    total_lines = _line_count(markdown_with_markers)

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
