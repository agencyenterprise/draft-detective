"""Files document processing never converted are loaded through its converter.

Document processing converts only the current revision's files, so a memo on
another revision can reach the agent's file tree uncached. Loading it must go
through the same converter (which turns a legacy .doc into .docx first and picks
the converter by role) and cache the result, rather than hand the raw file to
MarkItDown, which cannot read .doc.
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


def _file(markdown: str | None) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        file_name="response.doc",
        file_path="/uploads/response.doc",
        file_type="application/msword",
        file_size=1,
        content_hash="hash",
        role=FileRole.RESPONSE_MEMO,
        revision=1,
        markdown=markdown,
    )


def _document(file: File, markdown: str) -> FileDocument:
    return FileDocument(
        file_id=str(file.id),
        file_name=file.file_name,
        file_path=file.file_path,
        file_type=file.file_type,
        markdown=markdown,
        markdown_token_count=1,
    )


@pytest.mark.asyncio
async def test_uncached_file_goes_through_the_pipeline_converter_and_is_cached():
    file = _file(markdown=None)
    service = FileArtifactsService(project_id=str(file.project_id), revision=2)
    converter = AsyncMock(return_value=_document(file, "Author response: done."))

    with (
        patch(f"{MODULE}.load_file_document", new=AsyncMock(return_value=_document(file, ""))),
        patch(f"{MODULE}.convert_file_document_to_markdown", new=converter),
        patch(f"{MODULE}.update_file_artifacts", new=AsyncMock()) as cache,
    ):
        document = await service._load_file_document_with_markdown(file)

    assert document.markdown == "Author response: done."
    assert converter.await_args is not None
    assert converter.await_args.kwargs["role"] == FileRole.RESPONSE_MEMO
    cache.assert_awaited_once_with(file_id=str(file.id), markdown="Author response: done.")


@pytest.mark.asyncio
async def test_cached_file_is_not_converted_again():
    file = _file(markdown="Cached reply.")
    service = FileArtifactsService(project_id=str(file.project_id), revision=2)
    converter = AsyncMock()

    with (
        patch(f"{MODULE}.load_file_document", new=AsyncMock(return_value=_document(file, "Cached reply."))),
        patch(f"{MODULE}.convert_file_document_to_markdown", new=converter),
    ):
        document = await service._load_file_document_with_markdown(file)

    assert document.markdown == "Cached reply."
    converter.assert_not_awaited()
