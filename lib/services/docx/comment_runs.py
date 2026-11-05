"""The python-docx runs a comment covers, split so it covers exact characters.

python-docx anchors a comment on whole runs: the range starts before the first
run and ends after the last. A passage rarely starts and ends on a run
boundary, so the runs at its edges are split there -- each half keeps the
run's formatting -- and the comment covers exactly the passage.

Only a plain text run (formatting plus one ``w:t``) is split. A run carrying
anything else, such as a tab, a break, a footnote reference or a drawing, is
included whole instead, so nothing but text is ever rewritten; the comment then
covers a few characters more than the passage.

The characters are found in the runs python-docx shows, hyperlinks included.
That is not always the text docx-editor located the passage in (a field, a
content control, an earlier tracked insertion), so the anchor's repeat count
is checked first, and any disagreement returns None: the caller anchors the
comment on the whole paragraph rather than on the wrong words.
"""

import copy

from docx.oxml.ns import qn
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from lib.services.text.location import all_offsets

_PLAIN_RUN_CHILDREN = {qn("w:rPr"), qn("w:t")}


def _visible_runs(paragraph: Paragraph) -> list[Run]:
    """The paragraph's runs in order, the ones inside hyperlinks included."""
    runs: list[Run] = []
    for item in paragraph.iter_inner_content():
        runs.extend(item.runs if isinstance(item, Hyperlink) else [item])
    return runs


def _is_plain(run: Run) -> bool:
    children = list(run._r)
    return (
        all(child.tag in _PLAIN_RUN_CHILDREN for child in children)
        and sum(child.tag == qn("w:t") for child in children) == 1
    )


def _split(run: Run, offset: int) -> Run:
    """Cut a plain run at `offset`; returns the second half, placed after it."""
    text = run.text
    second = copy.deepcopy(run._r)
    run._r.addnext(second)
    run.text = text[:offset]
    tail = Run(second, run._parent)
    tail.text = text[offset:]
    return tail


def _split_at(paragraph: Paragraph, at: int) -> None:
    """Split the plain run straddling text offset `at`, if there is one."""
    position = 0
    for run in _visible_runs(paragraph):
        start, end = position, position + len(run.text)
        if start < at < end and _is_plain(run):
            _split(run, at - start)
            return
        position = end


def _covering(paragraph: Paragraph, start: int, end: int) -> list[Run]:
    """The runs holding any character of ``[start, end)``, in order."""
    covering: list[Run] = []
    position = 0
    for run in _visible_runs(paragraph):
        run_start, run_end = position, position + len(run.text)
        position = run_end
        if run_end > start and run_start < end:
            covering.append(run)
    return covering


def anchored_runs(
    paragraph: Paragraph, find: str, occurrence: int, total: int
) -> list[Run] | None:
    """The first and last run covering the `occurrence`-th `find`, or None.

    `total` is how many times docx-editor saw `find` in the paragraph; a
    different count here means the two libraries read the paragraph
    differently, and `occurrence` cannot be trusted.
    """
    text = "".join(run.text for run in _visible_runs(paragraph))
    offsets = all_offsets(text, find)
    if not find or len(offsets) != total or occurrence >= len(offsets):
        return None
    start = offsets[occurrence]
    end = start + len(find)
    _split_at(paragraph, start)
    _split_at(paragraph, end)
    covering = _covering(paragraph, start, end)
    if not covering:
        return None
    return [covering[0], covering[-1]]
