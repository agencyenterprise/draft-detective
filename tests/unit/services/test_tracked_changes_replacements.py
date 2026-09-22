"""Tests for the text a replacement reaches Word as.

Whitespace is written exactly as the edit wrote it, and a replacement Word
cannot represent is reported instead of approximated.
"""

from pathlib import Path
from typing import Dict, Tuple

import pytest
from docx import Document as PythonDocxDocument

from lib.models.issue_edit import IssueEdit
from lib.services.docx.tracked_changes import apply_tracked_changes

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
    document = PythonDocxDocument()
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
