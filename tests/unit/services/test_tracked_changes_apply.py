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
