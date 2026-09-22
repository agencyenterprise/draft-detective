"""Tests for writing the planned redlines into the file.

What the output still reads as afterwards, what an existing redline does to the
paragraph mapping, and what happens when the two libraries disagree about the
document at all.
"""

from pathlib import Path
from typing import Dict, Tuple

import pytest
from docx import Document as PythonDocxDocument
from docx_editor import Document as EditorDocument, EditOperation

from lib.services.docx.tracked_changes import apply_tracked_changes

from tests.unit.services.tracked_changes_support import (
    BODY as _BODY,
    docx_path,  # noqa: F401 -- a fixture, reached by name
    make_edit as _edit,
    plan_edits as _plan,
    read_document as _read,
    statuses as _statuses,
)


class TestTheFileStaysReadable:
    @pytest.mark.asyncio
    async def test_python_docx_reopens_the_output_with_untouched_text_intact(
        self, docx_path: Path
    ):
        edits = [
            _edit("14% rise", "18% rise", 1),
            _edit("**Figure 3**", "Figure 4", 2),
        ]

        plan, _ = await _plan(docx_path, edits)
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        paragraphs = [
            p.text
            for p in PythonDocxDocument(str(docx_path)).paragraphs
            if p.text.strip()
        ]
        # The redlined paragraphs no longer read as plain text to python-docx --
        # which is exactly why the comment pass has to run first -- but the
        # untouched one is unchanged.
        assert _BODY[2] in paragraphs

    @pytest.mark.asyncio
    async def test_an_empty_plan_leaves_the_file_alone(self, docx_path: Path):
        before = docx_path.read_bytes()

        assert await apply_tracked_changes(str(docx_path), []) == []
        assert docx_path.read_bytes() == before


# Two paragraphs reading alike, the first of which already carries someone
# else's tracked insertion. python-docx leaves an inserted run out of
# `paragraph.text`, so the two are indistinguishable by text on its side while
# docx-editor shows the insertion -- the case that made the old text-based
# mapping hand the redline to the wrong paragraph.
_ALIKE = "The results are significant."
_ALIKE_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 1), 1: (2, 2)}


@pytest.fixture
def alike_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_ALIKE)
    document.add_paragraph(_ALIKE)
    path = tmp_path / "alike.docx"
    document.save(str(path))

    doc = EditorDocument.open(
        path, author="Someone else", workspace_dir=str(tmp_path / "prior-ws")
    )
    try:
        first = doc.list_paragraphs_structured(limit=None)[0]
        doc.batch_edit(
            [
                EditOperation.replace(
                    "The results", "New The results", paragraph=first.ref
                )
            ]
        )
        doc.save()
    finally:
        doc.close()
    return path


class TestAnExistingRedlineDoesNotMisdirectTheNewOne:
    @pytest.mark.asyncio
    async def test_the_edit_lands_on_the_paragraph_its_line_names(
        self, alike_docx_path: Path
    ):
        edit = _edit("results", "findings", 1)

        plan, _ = await _plan(
            alike_docx_path,
            [edit],
            paragraph_line_ranges=_ALIKE_LINE_RANGES,
            markdown="\n".join([_ALIKE, _ALIKE]),
        )
        await apply_tracked_changes(
            str(alike_docx_path),
            plan.planned,
            workspace_root=str(alike_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        # Paragraph 1 is the one that carried the earlier insertion.
        doc = EditorDocument.open(
            alike_docx_path,
            author="Reader",
            workspace_dir=str(alike_docx_path.parent / "check-ws"),
        )
        try:
            texts = [info.text for info in doc.list_paragraphs_structured(limit=None)]
        finally:
            doc.close()
        assert texts == ["New The findings are significant.", _ALIKE]


class TestParagraphsThatCannotBeMatched:
    @pytest.mark.asyncio
    async def test_disagreeing_paragraph_counts_place_nothing(
        self, docx_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        original = EditorDocument.list_paragraphs_structured

        def one_short(self, **kwargs):  # type: ignore[no-untyped-def]
            return original(self, **kwargs)[:-1]

        monkeypatch.setattr(EditorDocument, "list_paragraphs_structured", one_short)
        edit = _edit("14% rise", "18% rise", 1)

        plan, _ = await _plan(docx_path, [edit])
        await apply_tracked_changes(
            str(docx_path), plan.planned, workspace_root=str(docx_path.parent)
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "not_found"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the document's paragraphs could not be matched to the file being "
            "exported"
        ]


# One Word paragraph holding a hard line break, which MarkItDown converts to
# two markdown lines. Both lines end on the same figure, so the edit's stored
# occurrence -- counted on its own line, where the figure is unique -- says
# nothing about which of the paragraph's two spans it means.
_BROKEN_LINES = ["First cohort rose 14%.", "Second cohort rose 14%."]
_BROKEN_MARKDOWN = "\n".join(_BROKEN_LINES)
_BROKEN_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 2)}


@pytest.fixture
def hard_break_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    paragraph = document.add_paragraph()
    first = paragraph.add_run(_BROKEN_LINES[0])
    first.add_break()
    paragraph.add_run(_BROKEN_LINES[1])
    path = tmp_path / "hard-break.docx"
    document.save(str(path))
    return path


class TestAParagraphSpanningSeveralMarkdownLines:
    async def _plan_broken(self, path: Path, line: int):
        edit = _edit("14%", "18%", line)
        plan, _ = await _plan(
            path,
            [edit],
            paragraph_line_ranges=_BROKEN_LINE_RANGES,
            markdown=_BROKEN_MARKDOWN,
        )
        await apply_tracked_changes(
            str(path), plan.planned, workspace_root=str(path.parent)
        )
        return edit, plan

    @pytest.mark.asyncio
    async def test_an_edit_on_the_second_line_redlines_the_second_sentence(
        self, hard_break_docx_path: Path
    ):
        edit, plan = await self._plan_broken(hard_break_docx_path, 2)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, original, _ = _read(hard_break_docx_path)
        assert "First cohort rose 14%." in visible
        assert "Second cohort rose 18%." in visible
        assert "Second cohort rose 14%." in original

    @pytest.mark.asyncio
    async def test_an_edit_on_the_first_line_redlines_the_first_sentence(
        self, hard_break_docx_path: Path
    ):
        edit, plan = await self._plan_broken(hard_break_docx_path, 1)

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(hard_break_docx_path)
        assert "First cohort rose 18%." in visible
        assert "Second cohort rose 14%." in visible


# The same paragraph with a space before the break, so the join puts a real
# space where the two lines meet. The quote then has an occurrence the Word
# paragraph carries but neither markdown line does: "14% in" straddles the
# break in "rose 14% | in 2019", and is line 2's own words in "rose 14% in
# 2020".
_STRADDLE_RUNS = ["First cohort rose 14% ", "in 2019; second cohort rose 14% in 2020."]
_STRADDLE_MARKDOWN = "\n".join(["First cohort rose 14%", _STRADDLE_RUNS[1]])
_STRADDLE_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 2)}


@pytest.fixture
def straddle_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    paragraph = document.add_paragraph()
    first = paragraph.add_run(_STRADDLE_RUNS[0])
    first.add_break()
    paragraph.add_run(_STRADDLE_RUNS[1])
    path = tmp_path / "straddle.docx"
    document.save(str(path))
    return path


class TestAQuoteThatStraddlesAHardBreak:
    @pytest.mark.asyncio
    async def test_the_edit_lands_inside_its_own_line_not_across_the_break(
        self, straddle_docx_path: Path
    ):
        # Unique on line 2, and the paragraph's *first* "14% in" is the one
        # the break invented. Counting the quote line by line never sees it.
        edit = _edit("14% in", "18% in", 2)

        plan, _ = await _plan(
            straddle_docx_path,
            [edit],
            paragraph_line_ranges=_STRADDLE_LINE_RANGES,
            markdown=_STRADDLE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(straddle_docx_path),
            plan.planned,
            workspace_root=str(straddle_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(straddle_docx_path)
        assert "First cohort rose 14% in 2019" in visible
        assert "second cohort rose 18% in 2020." in visible


# Two markdown lines reading exactly alike inside one paragraph: locating the
# edit's line is not enough on its own, since the paragraph carries it twice.
_TWIN_LINES = ["Rose 14%.", "Rose 14%."]
_TWIN_MARKDOWN = "\n".join(_TWIN_LINES)
_TWIN_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 2)}


@pytest.fixture
def twin_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    paragraph = document.add_paragraph()
    first = paragraph.add_run(_TWIN_LINES[0])
    first.add_break()
    paragraph.add_run(_TWIN_LINES[1])
    path = tmp_path / "twin.docx"
    document.save(str(path))
    return path


class TestTwoIdenticalLinesInOneParagraph:
    @pytest.mark.asyncio
    async def test_the_edit_lands_on_the_repeat_its_line_names(
        self, twin_docx_path: Path
    ):
        edit = _edit("14%", "18%", 2)

        plan, _ = await _plan(
            twin_docx_path,
            [edit],
            paragraph_line_ranges=_TWIN_LINE_RANGES,
            markdown=_TWIN_MARKDOWN,
        )
        await apply_tracked_changes(
            str(twin_docx_path), plan.planned, workspace_root=str(twin_docx_path.parent)
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(twin_docx_path)
        assert visible.strip() == "Rose 14%.Rose 18%."


# A range covering a second markdown line the Word paragraph does not carry:
# the line-range mapper runs a paragraph's range up to the line before the next
# one starts, so a line that merely reads alike falls inside it. The edit's own
# line cannot be located in the paragraph at all.
_DRIFTED_PARAGRAPH = "The committee recommends increasing the 2019 budget by 14%."
_DRIFTED_MARKDOWN = "\n".join(
    [_DRIFTED_PARAGRAPH, "The committee recommends increasing the 2020 budget by 9%."]
)
_DRIFTED_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 2)}


@pytest.fixture
def drifted_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_DRIFTED_PARAGRAPH)
    path = tmp_path / "drifted.docx"
    document.save(str(path))
    return path


# The same shape, with the quote repeated in the paragraph: nothing says which
# of the two the edit meant once its line cannot be found.
_REPEATED_PARAGRAPH = "Cohort A rose 14%; cohort B rose 14%."
_REPEATED_MARKDOWN = "\n".join(
    [_REPEATED_PARAGRAPH, "Cohort A rose 18%; cohort B rose 14%."]
)


@pytest.fixture
def repeated_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_REPEATED_PARAGRAPH)
    path = tmp_path / "repeated.docx"
    document.save(str(path))
    return path


class TestALineTheParagraphDoesNotCarry:
    @pytest.mark.asyncio
    async def test_an_unambiguous_quote_is_still_applied(self, drifted_docx_path: Path):
        edit = _edit("committee recommends", "board recommends", 2)

        plan, _ = await _plan(
            drifted_docx_path,
            [edit],
            paragraph_line_ranges=_DRIFTED_LINE_RANGES,
            markdown=_DRIFTED_MARKDOWN,
        )
        await apply_tracked_changes(
            str(drifted_docx_path),
            plan.planned,
            workspace_root=str(drifted_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(drifted_docx_path)
        assert "The board recommends increasing the 2019 budget" in visible

    @pytest.mark.asyncio
    async def test_a_repeated_quote_is_reported_rather_than_guessed_at(
        self, repeated_docx_path: Path
    ):
        edit = _edit("14%", "18%", 2)

        plan, _ = await _plan(
            repeated_docx_path,
            [edit],
            paragraph_line_ranges=_DRIFTED_LINE_RANGES,
            markdown=_REPEATED_MARKDOWN,
        )
        await apply_tracked_changes(
            str(repeated_docx_path),
            plan.planned,
            workspace_root=str(repeated_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "ambiguous"}
        visible, _, revisions = _read(repeated_docx_path)
        assert visible.strip() == _REPEATED_PARAGRAPH
        assert list(revisions) == []
