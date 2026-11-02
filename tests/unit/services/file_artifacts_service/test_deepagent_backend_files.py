"""Layout of the project file tree mounted into DeepAgent workflows.

Workflows point the agent at fixed paths, so where each role lands is part of
the contract. No DB: the file query and markdown loading are patched.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.files.document import FileDocument

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
async def test_every_revision_and_source_mounts_by_its_role():
    files = [
        _file(FileRole.MAIN, 1),
        _file(FileRole.MAIN, 2),
        _file(FileRole.SUPPORT, None),
    ]
    main_doc = _document(files[1])
    service = FileArtifactsService(project_id=str(uuid.uuid4()), revision=2)
    query = AsyncMock(return_value=files)

    with (
        patch(f"{MODULE}.get_files_by_project_id", new=query),
        patch.object(service, "get_main_file", new=AsyncMock(return_value=main_doc)),
        patch.object(
            service,
            "_load_file_document_with_markdown",
            new=AsyncMock(side_effect=_document),
        ),
    ):
        tree = await service.get_deepagent_backend_files(include_skills=False)

    assert set(tree) == {
        "/main.md",
        "/revisions/1/main.md",
        "/revisions/2/main.md",
        f"/supporting/{files[2].id}.md",
    }
    # Review Assistant documents are mounted by that workflow alone, from the
    # files its request names, so the shared tree never asks for them.
    assert query.call_args.kwargs["roles"] == [FileRole.MAIN, FileRole.SUPPORT]


@pytest.mark.asyncio
async def test_a_document_that_will_not_load_is_reported_not_raised():
    good, bad = _file(FileRole.REVIEW_INPUT, None), _file(FileRole.REVIEW_INPUT, None)
    service = FileArtifactsService(project_id=str(uuid.uuid4()), revision=1)

    async def load(file: File) -> FileDocument:
        if file is bad:
            raise ValueError("not a zip file")
        return _document(file)

    with (
        patch(
            f"{MODULE}.get_files_by_project_id", new=AsyncMock(return_value=[good, bad])
        ),
        patch.object(
            service,
            "_load_file_document_with_markdown",
            new=AsyncMock(side_effect=load),
        ),
    ):
        loaded = await service.get_file_documents(
            [str(bad.id), str(good.id), "not-in-project"]
        )

    assert [d.file_id for d in loaded.documents] == [str(good.id)]
    broken, gone = loaded.unreadable
    assert (broken.file_id, broken.reason) == (str(bad.id), "not a zip file")
    # Named by the request but no longer in the project: deleted since it started.
    assert (gone.file_id, gone.reason) == (
        "not-in-project",
        "it was deleted from the project.",
    )
