"""Tests for deciding whether an edit's line is the mapped paragraph's own.

A footnote reference the paragraph carries as a mark, a citation it shows as
text, a paragraph too short for the shared-prefix rule to help: what counts as
the same passage and what does not.
"""

from pathlib import Path

import pytest

from lib.services.docx.tracked_changes import apply_tracked_changes

from tests.unit.services.lean_docx import new_document
from tests.unit.services.tracked_changes_support import (
    OTHER_PASSAGE_DETAIL as _OTHER_PASSAGE_DETAIL,
    make_edit as _edit,
    plan_edits as _plan,
    read_document as _read,
    statuses as _statuses,
)

_FOOTNOTE_PARAGRAPH = "The protocol was applied to the second cohort in 2019."
_FOOTNOTE_MARKDOWN = (
    "The protocol was applied to the second cohort [[1]](#footnote-2) in 2019."
)


@pytest.fixture
def footnote_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_FOOTNOTE_PARAGRAPH)
    path = tmp_path / "footnote.docx"
    document.save(str(path))
    return path


# A bracketed citation Word shows as text, in both the line and the paragraph.
_CITATION_PARAGRAPH = "See [1] for further details."


@pytest.fixture
def citation_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_CITATION_PARAGRAPH)
    path = tmp_path / "citation.docx"
    document.save(str(path))
    return path


class TestAFootnoteReferenceIsNotDrift:
    @pytest.mark.asyncio
    async def test_a_marker_in_the_middle_of_the_line_still_allows_the_edit(
        self, footnote_docx_path: Path
    ):
        # Word carries the footnote as a reference mark, so the marker is on
        # the markdown line and nowhere in the paragraph's text.
        edit = _edit("second cohort", "third cohort", 1)

        plan, _ = await _plan(
            footnote_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_FOOTNOTE_MARKDOWN,
        )
        await apply_tracked_changes(
            str(footnote_docx_path),
            plan.planned,
            workspace_root=str(footnote_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(footnote_docx_path)
        assert "applied to the third cohort in 2019." in visible

    @pytest.mark.asyncio
    async def test_a_reference_style_marker_is_dropped_too(
        self, footnote_docx_path: Path
    ):
        edit = _edit("second cohort", "third cohort", 1)

        plan, _ = await _plan(
            footnote_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_FOOTNOTE_PARAGRAPH.replace("cohort", "cohort[^1]"),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}

    @pytest.mark.asyncio
    async def test_a_bracketed_citation_the_paragraph_shows_is_kept(
        self, citation_docx_path: Path
    ):
        # `[1]` here is a visible citation, not a footnote reference: Word
        # carries it as text, so dropping it from the line would make the line
        # and its own paragraph look like different passages.
        edit = _edit("further details", "the appendix", 1)

        plan, _ = await _plan(
            citation_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_CITATION_PARAGRAPH,
        )
        await apply_tracked_changes(
            str(citation_docx_path),
            plan.planned,
            workspace_root=str(citation_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(citation_docx_path)
        assert "See [1] for the appendix." in visible


# A nested block whose line opens with the same boilerplate as the paragraph
# above it and then says something else entirely. It shares 27 leading
# characters, which the old prefix rule took as proof of the same passage.
_BOILERPLATE_PARAGRAPH = (
    "The committee reviewed the budget for the western region in detail."
)
_BOILERPLATE_LINE = "The committee reviewed the appendix tables and the reviewer memos."


@pytest.fixture
def boilerplate_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_BOILERPLATE_PARAGRAPH)
    path = tmp_path / "boilerplate.docx"
    document.save(str(path))
    return path


class TestASharedOpeningIsNotTheSamePassage:
    @pytest.mark.asyncio
    async def test_a_line_that_only_starts_alike_is_rejected(
        self, boilerplate_docx_path: Path
    ):
        # The paragraph carries the quote too, so a wrong accept would redline
        # it rather than fail visibly.
        edit = _edit("committee", "steering group", 1)

        plan, _ = await _plan(
            boilerplate_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_BOILERPLATE_LINE,
        )
        await apply_tracked_changes(
            str(boilerplate_docx_path),
            plan.planned,
            workspace_root=str(boilerplate_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unlocatable"}
        assert [outcome.detail for outcome in plan.outcomes] == [_OTHER_PASSAGE_DETAIL]
        visible, _, revisions = _read(boilerplate_docx_path)
        assert visible.strip() == _BOILERPLATE_PARAGRAPH
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_a_line_that_drifts_mid_paragraph_is_still_accepted(
        self, boilerplate_docx_path: Path
    ):
        # The same paragraph, with the trailing clause MarkItDown writes and
        # Word does not show: alike over its whole length, so it belongs.
        edit = _edit("western region", "eastern region", 1)

        plan, _ = await _plan(
            boilerplate_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_BOILERPLATE_PARAGRAPH[:-1] + ", per Table 2.",
        )
        await apply_tracked_changes(
            str(boilerplate_docx_path),
            plan.planned,
            workspace_root=str(boilerplate_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(boilerplate_docx_path)
        assert "budget for the eastern region in detail." in visible


_SHORT_PARAGRAPH = "Yield rose 14%."


@pytest.fixture
def short_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_SHORT_PARAGRAPH)
    path = tmp_path / "short.docx"
    document.save(str(path))
    return path


class TestAShortParagraphHasNoPrefixToFallBackOn:
    @pytest.mark.asyncio
    async def test_a_line_that_merely_shares_the_quote_is_rejected(
        self, short_docx_path: Path
    ):
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown="Costs fell 14%.",
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unlocatable"}
        assert [outcome.detail for outcome in plan.outcomes] == [_OTHER_PASSAGE_DETAIL]

    @pytest.mark.asyncio
    async def test_its_own_line_is_accepted(self, short_docx_path: Path):
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_SHORT_PARAGRAPH,
        )
        await apply_tracked_changes(
            str(short_docx_path),
            plan.planned,
            workspace_root=str(short_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(short_docx_path)
        assert "Yield rose 18%." in visible

    @pytest.mark.asyncio
    async def test_a_leading_footnote_marker_is_not_counted_against_it(
        self, short_docx_path: Path
    ):
        # Too short for the shared-prefix rule to help, and the marker sits
        # where a prefix would start: only dropping it settles the line.
        edit = _edit("14%", "18%", 1)

        plan, _ = await _plan(
            short_docx_path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=f"[[1]](#footnote-2) {_SHORT_PARAGRAPH}",
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
