"""get_main_file_id / get_processed_supporting_file_ids read the file table, so
workflow initial states no longer depend on the last document_processing run
having seen every file (a file saved by reference_downloader after that run,
say). Only supporting files with cached markdown count as processed: a file
whose conversion failed has none, and summarization / reference matching
would abort trying to read it."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from lib.models.file import File, FileRole
from lib.services.files import get_main_file_id, get_processed_supporting_file_ids


def _file(role: FileRole, revision: int | None, markdown: str | None = "# md") -> File:
    return File(
        id=uuid4(),
        project_id=uuid4(),
        file_name=f"{role.value}.pdf",
        file_path="/tmp/x",
        file_type="application/pdf",
        file_size=1,
        content_hash="h",
        role=role,
        uploaded_by=uuid4(),
        revision=revision,
        markdown=markdown,
    )


@pytest.mark.asyncio
async def test_get_main_file_id_returns_the_revision_main_file():
    main = _file(FileRole.MAIN, revision=2)
    with patch(
        "lib.services.files.get_files_by_project_id",
        new=AsyncMock(return_value=[main]),
    ) as lookup:
        assert await get_main_file_id(main.project_id, 2) == str(main.id)

    lookup.assert_awaited_once_with(main.project_id, roles=[FileRole.MAIN], revision=2)


@pytest.mark.asyncio
async def test_get_main_file_id_raises_when_the_revision_has_no_main_file():
    with patch(
        "lib.services.files.get_files_by_project_id", new=AsyncMock(return_value=[])
    ):
        with pytest.raises(ValueError, match="No main file found"):
            await get_main_file_id(uuid4(), 1)


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_lists_files_with_cached_markdown():
    a, b = _file(FileRole.SUPPORT, None), _file(FileRole.SUPPORT, None)
    with patch(
        "lib.services.files.get_files_by_project_id",
        new=AsyncMock(return_value=[a, b]),
    ) as lookup:
        assert await get_processed_supporting_file_ids(a.project_id, 1) == [
            str(a.id),
            str(b.id),
        ]

    lookup.assert_awaited_once_with(a.project_id, roles=[FileRole.SUPPORT], revision=1)


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_skips_files_without_cached_markdown():
    """A supporting file whose conversion failed keeps its row but has no
    markdown. It must be left out so consumers do not abort on it."""
    ok = _file(FileRole.SUPPORT, None)
    failed = _file(FileRole.SUPPORT, None, markdown=None)
    with patch(
        "lib.services.files.get_files_by_project_id",
        new=AsyncMock(return_value=[failed, ok]),
    ):
        assert await get_processed_supporting_file_ids(ok.project_id, 1) == [str(ok.id)]


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_is_empty_without_support_files():
    with patch(
        "lib.services.files.get_files_by_project_id", new=AsyncMock(return_value=[])
    ):
        assert await get_processed_supporting_file_ids(uuid4(), 1) == []
