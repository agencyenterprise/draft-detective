"""Tests for the proposed-edit half of a DOCX export, driven from Issue rows."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

import pytest
from docx import Document as PythonDocxDocument
from docx_editor import Document as EditorDocument

from lib.models.issue import Issue
from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.services.docx.edit_export import apply_edit_export, plan_edit_export
from lib.workflows.models import SeverityEnum, WorkflowRunType

_PARAGRAPH = "The chapter reports a 14% rise in output for 2019."
_MARKDOWN = _PARAGRAPH


@pytest.fixture
def docx_path(tmp_path: Path) -> Path:
    document = PythonDocxDocument()
    document.add_paragraph(_PARAGRAPH)
    path = tmp_path / "main.docx"
    document.save(str(path))
    return path


def _edit(
    original_text: str,
    replacement_text: str,
    *,
    status: IssueEditStatus = IssueEditStatus.PROPOSED,
) -> IssueEdit:
    return IssueEdit(
        id=uuid.uuid4(),
        issue_id=uuid.uuid4(),
        position=0,
        original_text=original_text,
        replacement_text=replacement_text,
        start_line=1,
        end_line=1,
        rationale="the figure is wrong",
        status=status,
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


def _visible(path: Path) -> str:
    doc = EditorDocument.open(
        path, author="Reader", workspace_dir=str(path.parent / "read-ws")
    )
    try:
        return doc.get_visible_text()
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
    await apply_edit_export(
        str(docx_path), plan, "project-1", workspace_root=str(tmp_path)
    )

    assert plan.notes_for(issue.id) == [
        'Proposed edit: "14% rise" → "18% rise"\n'
        "the figure is wrong\n"
        "Applied below as a tracked change."
    ]
    assert "reports a 18% rise" in _visible(docx_path)


@pytest.mark.asyncio
async def test_without_a_paragraph_mapping_nothing_is_written_and_the_note_says_so(
    docx_path: Path, tmp_path: Path
):
    issue = _issue([_edit("14% rise", "18% rise")])
    before = docx_path.read_bytes()

    plan = await plan_edit_export(
        [issue], _MARKDOWN, str(docx_path), {}, workspace_root=str(tmp_path)
    )
    await apply_edit_export(
        str(docx_path), plan, "project-1", workspace_root=str(tmp_path)
    )

    assert plan.planned == []
    assert plan.notes_for(issue.id)[0].endswith(
        "Not applied as a tracked change: the quoted text could not be "
        "matched in this paragraph."
    )
    assert docx_path.read_bytes() == before


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
