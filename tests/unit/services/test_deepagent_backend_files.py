"""Layout of the project file tree mounted into DeepAgent workflows.

Workflows point the agent at fixed paths, so where each role lands is part of
the contract. No DB: the file query and markdown loading are patched.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)

MODULE = "lib.services.file_artifacts_service.file_artifacts_service"


def _file(role: FileRole, revision: int | None) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        file_name=f"{role.value}.docx",
        file_path="/uploads/x.docx",
        file_type="application/docx",
        file_size=1,
        content_hash="hash",
        role=role,
        revision=revision,
    )


def _document(file: File) -> FileDocument:
    return FileDocument(
        file_id=str(file.id),
        file_name=file.file_name,
        file_path=file.file_path,
        file_type=file.file_type,
        markdown=f"{file.role.value} r{file.revision}",
        markdown_token_count=1,
    )


@pytest.mark.asyncio
async def test_memos_mount_under_their_revision_folder():
    files = [
        _file(FileRole.MAIN, 1),
        _file(FileRole.MAIN, 2),
        _file(FileRole.REVIEWER_MEMO, 1),
        _file(FileRole.RESPONSE_MEMO, 2),
    ]
    main_doc = _document(files[1])
    service = FileArtifactsService(project_id=str(uuid.uuid4()), revision=2)

    with (
        patch(f"{MODULE}.get_files_by_project_id", new=AsyncMock(return_value=files)),
        patch.object(service, "get_main_file", new=AsyncMock(return_value=main_doc)),
        patch.object(
            service,
            "_load_file_document_with_markdown",
            new=AsyncMock(side_effect=_document),
        ),
    ):
        tree = await service.get_deepagent_backend_files(include_skills=False)

    reviewer, response = files[2], files[3]
    assert set(tree) == {
        "/main.md",
        "/revisions/1/main.md",
        "/revisions/2/main.md",
        f"/revisions/1/reviewer-memos/{reviewer.id}.md",
        f"/revisions/2/response-memos/{response.id}.md",
    }


@pytest.mark.asyncio
async def test_input_files_mount_only_the_picked_files_by_slot():
    project_id = uuid.uuid4()
    draft, memo = _file(FileRole.MAIN, 1), _file(FileRole.SUPPORT, None)
    for f in (draft, memo):
        f.project_id = project_id
    by_id = {str(f.id): f for f in (draft, memo)}
    service = FileArtifactsService(project_id=str(project_id), revision=2)

    with (
        patch(
            f"{MODULE}.get_file_by_id",
            new=AsyncMock(side_effect=lambda file_id: by_id[file_id]),
        ),
        patch.object(
            service,
            "_load_file_document_with_markdown",
            new=AsyncMock(side_effect=_document),
        ),
    ):
        tree = await service.get_input_backend_files(
            {"reviewed-draft": [str(draft.id)], "reviewer-memos": [str(memo.id)]},
            include_skills=False,
        )

    assert set(tree) == {
        f"/inputs/reviewed-draft/{draft.id}.md",
        f"/inputs/reviewer-memos/{memo.id}.md",
    }


@pytest.mark.asyncio
async def test_input_files_reject_another_projects_file():
    other = _file(FileRole.MAIN, 1)
    service = FileArtifactsService(project_id=str(uuid.uuid4()), revision=1)

    with patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=other)):
        with pytest.raises(ValueError, match="does not belong"):
            await service.get_input_backend_files(
                {"reviewed-draft": [str(other.id)]}, include_skills=False
            )
