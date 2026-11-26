"""A run's file artifacts open only its own project's files.

Agents pick file ids themselves: the citation validator's read_document and
search_document take whatever id the model passes, and the model reads ids in
documents their authors write. An id naming another project's file must read
as missing, never as that file's text or summary.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lib.agents.tools.read_document import read_document
from lib.agents.tools.search_document import search_document
from lib.models.file import File, FileRole
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)

MODULE = "lib.services.file_artifacts_service.file_artifacts_service"
SECRET = "Their unpublished finding"


def _file(project_id: uuid.UUID) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=project_id,
        file_name="draft.docx",
        file_path="/uploads/draft.docx",
        file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=1,
        content_hash="hash",
        role=FileRole.MAIN,
        revision=1,
        markdown=SECRET,
        markdown_token_count=4,
        has_cached_markdown=True,
        summary={
            "title": SECRET,
            "summary": SECRET,
            "authors": "A. Author",
            "publication_date": "2026",
            "abstract": SECRET,
        },
        has_cached_summary=True,
    )


def _service() -> FileArtifactsService:
    return FileArtifactsService(project_id=str(uuid.uuid4()), revision=1)


def _no_runs() -> AsyncMock:
    """The run state fallback, finding nothing: this project never saw the file."""
    return AsyncMock(return_value=(None, None))


@pytest.mark.asyncio
async def test_another_projects_file_is_not_found() -> None:
    service = _service()
    theirs = _file(project_id=uuid.uuid4())

    with (
        patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=theirs)),
        patch(f"{MODULE}.get_project_workflow_run_with_state", _no_runs()),
        pytest.raises(ValueError, match="No workflow run found"),
    ):
        await service.get_file_document(str(theirs.id))


@pytest.mark.asyncio
async def test_another_projects_summary_is_not_found() -> None:
    service = _service()
    theirs = _file(project_id=uuid.uuid4())

    with (
        patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=theirs)),
        patch(f"{MODULE}.get_project_workflow_run_with_state", _no_runs()),
        pytest.raises(ValueError, match="No workflow run found"),
    ):
        await service.get_file_summary(str(theirs.id))


@pytest.mark.asyncio
async def test_the_agent_tools_cannot_read_another_projects_file() -> None:
    service = _service()
    theirs = _file(project_id=uuid.uuid4())
    runtime = SimpleNamespace(context=SimpleNamespace(file_artifacts_service=service))

    with (
        patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=theirs)),
        patch(f"{MODULE}.get_project_workflow_run_with_state", _no_runs()),
    ):
        read = await read_document.coroutine(  # type: ignore[attr-defined]
            file_id=str(theirs.id), start_line=1, end_line=5, runtime=runtime
        )
        found = await search_document.coroutine(  # type: ignore[attr-defined]
            file_id=str(theirs.id), pattern="finding", runtime=runtime
        )

    assert SECRET not in read
    assert SECRET not in found


@pytest.mark.asyncio
async def test_the_projects_own_file_still_reads() -> None:
    service = _service()
    ours = _file(project_id=uuid.UUID(service.project_id))

    with patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=ours)):
        document = await service.get_file_document(str(ours.id))
        summary = await service.get_file_summary(str(ours.id))

    assert document.markdown == SECRET
    assert summary.summary == SECRET


@pytest.mark.asyncio
async def test_a_file_without_a_project_is_not_found() -> None:
    # Chat, Teams and Word attachments belong to no project.
    service = _service()
    attachment = _file(project_id=uuid.uuid4())
    attachment.project_id = None

    with (
        patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=attachment)),
        patch(f"{MODULE}.get_project_workflow_run_with_state", _no_runs()),
        pytest.raises(ValueError, match="No workflow run found"),
    ):
        await service.get_file_document(str(attachment.id))


@pytest.mark.asyncio
async def test_a_project_id_spelled_differently_still_reads_its_files() -> None:
    # Routes build the service from the id as the request spelled it.
    project_id = uuid.uuid4()
    service = FileArtifactsService(project_id=project_id.hex.upper(), revision=1)
    ours = _file(project_id=project_id)

    with patch(f"{MODULE}.get_file_by_id", AsyncMock(return_value=ours)):
        document = await service.get_file_document(str(ours.id))

    assert document.markdown == SECRET
