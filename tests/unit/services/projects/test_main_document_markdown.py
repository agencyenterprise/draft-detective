"""get_main_document_markdown reads the revision's own MAIN file, and answers
None while there is nothing to read yet."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.services.files.document import FileDocument
from lib.services.projects.service import get_main_document_markdown

MODULE = "lib.services.projects.service"
PROJECT_ID = str(uuid.uuid4())


def _main_file(revision: int) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=uuid.UUID(PROJECT_ID),
        file_name="main.docx",
        file_path="/uploads/main.docx",
        file_type="application/docx",
        file_size=1,
        content_hash="hash",
        role=FileRole.MAIN,
        revision=revision,
    )


def _document(file: File) -> FileDocument:
    return FileDocument(
        file_id=str(file.id),
        file_name=file.file_name,
        file_path=file.file_path,
        file_type=file.file_type,
        markdown="# Revision 2",
        markdown_token_count=2,
    )


@pytest.mark.asyncio
async def test_reads_the_markdown_of_the_revision_main_file():
    main = _main_file(2)
    get_document = AsyncMock(return_value=_document(main))
    with (
        patch(f"{MODULE}.find_main_file", new=AsyncMock(return_value=main)) as find,
        patch(f"{MODULE}.FileArtifactsService.get_file_document", new=get_document),
    ):
        assert await get_main_document_markdown(PROJECT_ID, 2) == "# Revision 2"

    find.assert_awaited_once_with(PROJECT_ID, 2)
    get_document.assert_awaited_once_with(str(main.id))


@pytest.mark.asyncio
async def test_is_none_before_the_main_document_is_uploaded():
    with patch(f"{MODULE}.find_main_file", new=AsyncMock(return_value=None)):
        assert await get_main_document_markdown(PROJECT_ID, 2) is None


@pytest.mark.asyncio
async def test_is_none_before_document_processing_has_converted_it():
    get_document = AsyncMock(side_effect=ValueError("no file document"))
    with (
        patch(f"{MODULE}.find_main_file", new=AsyncMock(return_value=_main_file(2))),
        patch(f"{MODULE}.FileArtifactsService.get_file_document", new=get_document),
    ):
        assert await get_main_document_markdown(PROJECT_ID, 2) is None
