"""Tests for the text a replacement reaches Word as.

Whitespace is written exactly as the edit wrote it, and a replacement Word
cannot represent is reported instead of approximated.
"""

from pathlib import Path
from typing import Dict, Tuple

import pytest

from lib.models.issue_edit import IssueEdit
from lib.services.docx.tracked_changes import apply_tracked_changes

from tests.unit.services.lean_docx import new_document
from tests.unit.services.tracked_changes_support import (
    make_edit as _edit,
    plan_edits as _plan,
    read_document as _read,
    statuses as _statuses,
)

_JOINED_MARKDOWN = "This is aword."
_JOINED_LINE_RANGES: Dict[int, Tuple[int, int]] = {0: (1, 1)}


@pytest.fixture
def joined_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_JOINED_MARKDOWN)
    path = tmp_path / "joined.docx"
    document.save(str(path))
    return path


class TestTheReplacementReachesWordAsWritten:
    async def _plan_joined(self, path: Path, edit: IssueEdit):
        return await _plan(
            path,
            [edit],
            paragraph_line_ranges=_JOINED_LINE_RANGES,
            markdown=_JOINED_MARKDOWN,
        )

    @pytest.mark.asyncio
    async def test_a_replacement_that_only_adds_a_space_keeps_it(
        self, joined_docx_path: Path
    ):
        edit = _edit("word", " word", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert plan.planned[0].replace_with == " word"
        visible, original, _ = _read(joined_docx_path)
        assert "This is a word." in visible
        assert "This is aword." in original

    @pytest.mark.asyncio
    async def test_a_double_space_in_the_replacement_reaches_the_page(
        self, joined_docx_path: Path
    ):
        # Word keeps every space of an inserted run, so nothing is collapsed
        # on the way in.
        edit = _edit("aword", "a  word", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert plan.planned[0].replace_with == "a  word"
        visible, original, _ = _read(joined_docx_path)
        assert "This is a  word." in visible
        assert "This is aword." in original

    @pytest.mark.asyncio
    async def test_a_replacement_carrying_a_tab_is_unsupported(
        self, joined_docx_path: Path
    ):
        edit = _edit("aword", "a\tword", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the replacement contains a tab"
        ]
        visible, _, revisions = _read(joined_docx_path)
        assert visible.strip() == "This is aword."
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_a_replacement_carrying_a_newline_is_unsupported(
        self, joined_docx_path: Path
    ):
        edit = _edit("aword", "a\nword", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)
        await apply_tracked_changes(
            str(joined_docx_path),
            plan.planned,
            workspace_root=str(joined_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the replacement spans more than one paragraph"
        ]
        visible, _, revisions = _read(joined_docx_path)
        assert visible.strip() == "This is aword."
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_a_replacement_that_only_reformats_the_text_is_unsupported(
        self, joined_docx_path: Path
    ):
        edit = _edit("aword", "**aword**", 1)

        plan, _ = await self._plan_joined(joined_docx_path, edit)

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "the replacement matches the current text once formatting is removed"
        ]


# A quote that takes the spaces around a word with it. The edit was written
# that way on purpose -- replacing " bad " with " good " and deleting " bad"
# both have to leave one space where there was one.
_SPACED_PARAGRAPH = "This is a bad result."


@pytest.fixture
def spaced_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_SPACED_PARAGRAPH)
    path = tmp_path / "spaced.docx"
    document.save(str(path))
    return path


class TestWhitespaceTheQuoteItselfCarries:
    async def _plan_spaced(self, path: Path, edit: IssueEdit):
        return await _plan(
            path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_SPACED_PARAGRAPH,
        )

    @pytest.mark.asyncio
    async def test_a_quote_with_spaces_on_both_sides_replaces_them_too(
        self, spaced_docx_path: Path
    ):
        edit = _edit(" bad ", " good ", 1)

        plan, _ = await self._plan_spaced(spaced_docx_path, edit)
        await apply_tracked_changes(
            str(spaced_docx_path),
            plan.planned,
            workspace_root=str(spaced_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        assert plan.planned[0].find == " bad "
        visible, _, _ = _read(spaced_docx_path)
        assert "This is a good result." in visible

    @pytest.mark.asyncio
    async def test_deleting_a_quote_with_a_leading_space_leaves_one_space(
        self, spaced_docx_path: Path
    ):
        edit = _edit(" bad", "", 1)

        plan, _ = await self._plan_spaced(spaced_docx_path, edit)
        await apply_tracked_changes(
            str(spaced_docx_path),
            plan.planned,
            workspace_root=str(spaced_docx_path.parent),
        )

        assert plan.planned[0].find == " bad"
        visible, _, _ = _read(spaced_docx_path)
        assert "This is a result." in visible

    @pytest.mark.asyncio
    async def test_a_quote_without_boundary_whitespace_is_unaffected(
        self, spaced_docx_path: Path
    ):
        edit = _edit("bad", "good", 1)

        plan, _ = await self._plan_spaced(spaced_docx_path, edit)
        await apply_tracked_changes(
            str(spaced_docx_path),
            plan.planned,
            workspace_root=str(spaced_docx_path.parent),
        )

        assert plan.planned[0].find == "bad"
        visible, _, _ = _read(spaced_docx_path)
        assert "This is a good result." in visible
