"""Tests for the proposed-edit half of a DOCX export, driven from Issue rows."""

import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_editor import BatchOperationError
from docx_editor import Document as EditorDocument

from lib.models.issue import Issue
from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.docx import edit_export
from lib.services.docx.edit_export import (
    EditExport,
    describe_edit_export,
    plan_edit_export,
    write_edit_export,
)
from lib.workflows.models import SeverityEnum, WorkflowRunType
from tests.unit.services.docx.lean_docx import new_document
from tests.unit.services.docx.tracked_changes.support import display_fields

_PARAGRAPH = "The chapter reports a 14% rise in output for 2019."
_MARKDOWN = _PARAGRAPH


@pytest.fixture
def docx_path(tmp_path: Path) -> Path:
    document = new_document()
    document.add_paragraph(_PARAGRAPH)
    path = tmp_path / "main.docx"
    document.save(str(path))
    return path


def _edit(
    original_text: str,
    replacement_text: str,
    *,
    status: IssueEditStatus = IssueEditStatus.PROPOSED,
    start_line: int = 1,
) -> IssueEdit:
    return IssueEdit(
        id=uuid.uuid4(),
        issue_id=uuid.uuid4(),
        position=0,
        original_text=original_text,
        replacement_text=replacement_text,
        start_line=start_line,
        end_line=start_line,
        rationale="the figure is wrong",
        status=status,
        # Plain prose either way, so the rendered columns read as the quote
        # itself; the reporter fills them from the markdown line.
        **display_fields(original_text, replacement_text, original_text),
    )


def _issue(edits: Sequence[IssueEdit]) -> Issue:
    now = datetime.now(UTC)
    issue = Issue(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workflow_run_id=uuid.uuid4(),
        issue_hash=uuid.uuid4().hex[:64],
        title="Reference has incorrect fields",
        description="The figure does not match the source.",
        severity=SeverityEnum.HIGH,
        workflow_type=WorkflowRunType.REFERENCE_VALIDATION_V2,
        start_line=1,
        end_line=1,
        created_at=now,
        updated_at=now,
    )
    issue.edit_rows = list(edits)
    return issue


class _CommentWriter:
    """Stands in for the comment pass: a fresh copy of the original per call.

    Keeps the export each call was handed, so a test can read the notes the
    delivered file's comments were written from.
    """

    def __init__(self, original: Path, directory: Path):
        self.original = original
        self.directory = directory
        self.exports: list[EditExport] = []
        self.paths: list[Path] = []

    async def __call__(self, export: EditExport) -> str:
        self.exports.append(export)
        path = self.directory / f"export-{len(self.paths)}.docx"
        shutil.copyfile(self.original, path)
        self.paths.append(path)
        return str(path)


async def _write(
    issues: Sequence[Issue], plan: EditExport, writer: _CommentWriter, tmp_path: Path
) -> Path:
    path = await write_edit_export(
        issues, plan, writer, "project-1", workspace_root=str(tmp_path)
    )
    return Path(path)


def _visible(path: Path) -> str:
    doc = EditorDocument.open(
        path, author="Reader", workspace_dir=str(path.parent / "read-ws")
    )
    try:
        return doc.get_visible_text()
    finally:
        doc.close()


def _revisions(path: Path) -> list[tuple[str, str]]:
    doc = EditorDocument.open(
        path, author="Reader", workspace_dir=str(path.parent / "revision-ws")
    )
    try:
        return [(r.type, r.text) for r in doc.list_revisions()]
    finally:
        doc.close()


@pytest.mark.asyncio
async def test_an_issues_edit_is_planned_noted_and_written(
    docx_path: Path, tmp_path: Path
):
    issue = _issue([_edit("14% rise", "18% rise")])

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(docx_path), {0: (1, 1)}, workspace_root=str(tmp_path)
    )
    output = await _write([issue], plan, _CommentWriter(docx_path, tmp_path), tmp_path)

    assert [n.status for n in plan.notes_for(issue.id)] == ["applied"]
    assert plan.notes_for(issue.id)[0].pointer == "“14%” → “18%”"
    assert "reports a 18% rise" in _visible(output)


@pytest.mark.asyncio
async def test_a_word_file_uploaded_under_a_doc_name_is_still_planned(
    docx_path: Path, tmp_path: Path
):
    doc_named = docx_path.with_suffix(".doc")
    docx_path.rename(doc_named)
    issue = _issue([_edit("14% rise", "18% rise")])

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(doc_named), {0: (1, 1)}, workspace_root=str(tmp_path)
    )

    assert plan.notes_for(issue.id)[0].status == "applied"


@pytest.mark.asyncio
async def test_without_a_paragraph_mapping_nothing_is_written_and_the_note_says_so(
    docx_path: Path, tmp_path: Path
):
    issue = _issue([_edit("14% rise", "18% rise")])
    before = docx_path.read_bytes()

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(docx_path), {}, workspace_root=str(tmp_path)
    )
    output = await _write([issue], plan, _CommentWriter(docx_path, tmp_path), tmp_path)

    assert plan.planned == []
    assert plan.notes_for(issue.id)[0].reason == (
        "the quoted text could not be matched in this paragraph"
    )
    assert output.read_bytes() == before


@pytest.mark.asyncio
async def test_a_rejected_edit_is_not_mentioned_at_all(docx_path: Path, tmp_path: Path):
    issue = _issue([_edit("14% rise", "18% rise", status=IssueEditStatus.REJECTED)])

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(docx_path), {0: (1, 1)}, workspace_root=str(tmp_path)
    )

    assert plan.planned == []
    assert plan.notes_for(issue.id) == []


@pytest.mark.asyncio
async def test_an_issue_without_edits_plans_nothing(docx_path: Path, tmp_path: Path):
    issue = _issue([])

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(docx_path), {0: (1, 1)}, workspace_root=str(tmp_path)
    )

    assert plan.planned == []
    assert plan.outcomes == {}
    assert plan.notes_by_issue == {}


_TWO_PARAGRAPHS = [
    "The chapter reports a 14% rise in output for 2019.",
    "The appendix lists every source consulted in full.",
]
_TWO_PARAGRAPH_MARKDOWN = "\n".join(_TWO_PARAGRAPHS)
_TWO_PARAGRAPH_RANGES = {0: (1, 1), 1: (2, 2)}


@pytest.fixture
def two_paragraph_docx_path(tmp_path: Path) -> Path:
    document = new_document()
    for text in _TWO_PARAGRAPHS:
        document.add_paragraph(text)
    path = tmp_path / "two-paragraphs.docx"
    document.save(str(path))
    return path


@pytest.fixture
def reject_the_appendix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make docx-editor refuse the appendix paragraph's operation, and only that.

    Stands in for anything the library rejects at apply time -- a stale hash, a
    search string the paragraph no longer carries. It bites on the first
    write; the second never asks for the operation again.
    """
    original = EditorDocument.batch_edit

    def batch_edit(self, operations, **kwargs):  # type: ignore[no-untyped-def]
        for index, operation in enumerate(operations):
            if operation.find == "every source":
                raise BatchOperationError(index, "text not found in paragraph")
        return original(self, operations, **kwargs)

    monkeypatch.setattr(EditorDocument, "batch_edit", batch_edit)


class TestTheWriteDecidesWhatTheCommentsClaim:
    async def _plan(self, path: Path, issues, workspace: Path):
        return await plan_edit_export(
            issues,
            _TWO_PARAGRAPH_MARKDOWN,
            str(path),
            _TWO_PARAGRAPH_RANGES,
            workspace_root=str(workspace),
        )

    @pytest.mark.asyncio
    async def test_an_edit_the_library_refuses_is_noted_as_failed_and_dropped(
        self, two_paragraph_docx_path: Path, tmp_path: Path, reject_the_appendix: None
    ):
        writable = _issue([_edit("14% rise", "18% rise")])
        refused = _issue(
            [_edit("every source", "every source and dataset", start_line=2)]
        )
        issues = [writable, refused]
        writer = _CommentWriter(two_paragraph_docx_path, tmp_path)

        plan = await self._plan(two_paragraph_docx_path, issues, tmp_path)
        output = await _write(issues, plan, writer, tmp_path)

        # The first file's comments promised both redlines, so it is replaced.
        assert writer.paths == [tmp_path / "export-0.docx", output]
        assert not writer.paths[0].exists()
        delivered = writer.exports[-1]
        (refused_note,) = delivered.notes_for(refused.id)
        assert refused_note.status == "not_applied"
        assert refused_note.reason == "text not found in paragraph"
        assert [edit.edit_id for edit in delivered.planned] == [
            writable.edit_rows[0].id
        ]
        assert [n.status for n in delivered.notes_for(writable.id)] == ["applied"]
        visible = _visible(output)
        assert "reports a 18% rise" in visible
        assert "lists every source consulted" in visible

    @pytest.mark.asyncio
    async def test_planning_leaves_the_original_alone_and_a_clean_write_happens_once(
        self, two_paragraph_docx_path: Path, tmp_path: Path
    ):
        issue = _issue([_edit("14% rise", "18% rise")])
        before = two_paragraph_docx_path.read_bytes()
        writer = _CommentWriter(two_paragraph_docx_path, tmp_path)

        plan = await self._plan(two_paragraph_docx_path, [issue], tmp_path)

        assert two_paragraph_docx_path.read_bytes() == before

        output = await _write([issue], plan, writer, tmp_path)

        assert writer.exports == [plan]
        assert [kind for kind, _ in _revisions(output)] == ["deletion", "insertion"]
        assert _visible(output).count("18% rise") == 1


class TestTheCommentsOnlyMode:
    def test_every_edit_is_described_without_opening_the_document(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("the comments-only mode must not open the document")

        monkeypatch.setattr(edit_export, "plan_tracked_changes", refuse)
        monkeypatch.setattr(edit_export, "apply_tracked_changes", refuse)
        issue = _issue([_edit("14% rise", "18% rise")])

        export = describe_edit_export([issue])

        assert export.planned == []
        (note,) = export.notes_for(issue.id)
        assert note.status == "skipped"
        assert note.fix == "Replace “14% rise” with “18% rise”"
        assert note.rationale == "the figure is wrong"

    def test_a_rejected_edit_is_still_left_out(self):
        issue = _issue(
            [
                _edit("14% rise", "18% rise"),
                _edit("for 2019", "for 2021", status=IssueEditStatus.REJECTED),
            ]
        )

        export = describe_edit_export([issue])

        assert len(export.outcomes) == 1
        assert len(export.notes_for(issue.id)) == 1
        assert export.outcomes[issue.edit_rows[0].id].status == "skipped"

    def test_an_issue_without_edits_says_nothing(self):
        issue = _issue([])

        export = describe_edit_export([issue])

        assert export.outcomes == {}
        assert export.notes_by_issue == {}


class TestAnEmptyPlanCostsNothing:
    @pytest.mark.asyncio
    async def test_nothing_to_write_opens_nothing_and_writes_once(
        self, docx_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("an empty plan must not open the document")

        # The quote is nowhere on its line, so the pre-flight plans nothing.
        issue = _issue([_edit("a 40% drop", "a 30% drop")])
        writer = _CommentWriter(docx_path, tmp_path)

        export = await plan_edit_export(
            [issue],
            _MARKDOWN,
            str(docx_path),
            {0: (1, 1)},
            workspace_root=str(tmp_path),
        )
        monkeypatch.setattr(EditorDocument, "open", refuse)
        output = await _write([issue], export, writer, tmp_path)

        assert export.planned == []
        assert export.notes_for(issue.id)[0].reason == (
            "the quoted text could not be matched in this paragraph"
        )
        assert writer.exports == [export]
        assert output.read_bytes() == docx_path.read_bytes()
