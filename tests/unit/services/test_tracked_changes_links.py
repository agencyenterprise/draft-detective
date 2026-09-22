"""Tests for an edit that would change where a link points.

Word keeps a hyperlink as a relationship of its own rather than as paragraph
text, so a redline over the label cannot move the target with it.
"""

from pathlib import Path

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

# A link whose label an edit rewrites. Word keeps the hyperlink itself out of
# the paragraph's text, so only the label can be redlined.
_LINK_PARAGRAPH = "See the Wrong report for details."
_LINK_MARKDOWN = "See the [Wrong report](https://x/wrong) for details."


@pytest.fixture
def link_docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_LINK_PARAGRAPH)
    path = tmp_path / "link.docx"
    document.save(str(path))
    return path


class TestALinkDestinationCannotBeRedlined:
    async def _plan_link(self, path: Path, edit: IssueEdit):
        return await _plan(
            path,
            [edit],
            paragraph_line_ranges={0: (1, 1)},
            markdown=_LINK_MARKDOWN,
        )

    @pytest.mark.asyncio
    async def test_a_replacement_pointing_somewhere_else_is_unsupported(
        self, link_docx_path: Path
    ):
        edit = _edit(
            "[Wrong report](https://x/wrong)",
            "[Correct report](https://x/correct)",
            1,
        )

        plan, _ = await self._plan_link(link_docx_path, edit)
        await apply_tracked_changes(
            str(link_docx_path),
            plan.planned,
            workspace_root=str(link_docx_path.parent),
        )

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}
        assert [outcome.detail for outcome in plan.outcomes] == [
            "it changes a link destination, which the export cannot write"
        ]
        visible, _, revisions = _read(link_docx_path)
        assert visible.strip() == _LINK_PARAGRAPH
        assert list(revisions) == []

    @pytest.mark.asyncio
    async def test_a_replacement_adding_a_link_is_unsupported_too(
        self, link_docx_path: Path
    ):
        edit = _edit("Wrong report", "[Wrong report](https://x/new)", 1)

        plan, _ = await self._plan_link(link_docx_path, edit)

        assert plan.planned == []
        assert _statuses(plan.outcomes) == {edit.id: "unsupported"}

    @pytest.mark.asyncio
    async def test_a_label_change_keeping_the_destination_is_written(
        self, link_docx_path: Path
    ):
        edit = _edit(
            "[Wrong report](https://x/wrong)",
            "[Correct report](https://x/wrong)",
            1,
        )

        plan, _ = await self._plan_link(link_docx_path, edit)
        await apply_tracked_changes(
            str(link_docx_path),
            plan.planned,
            workspace_root=str(link_docx_path.parent),
        )

        assert _statuses(plan.outcomes) == {edit.id: "applied"}
        visible, _, _ = _read(link_docx_path)
        assert "See the Correct report for details." in visible
