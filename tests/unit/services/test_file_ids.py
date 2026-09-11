"""get_main_file_id / get_processed_supporting_file_ids read the file table, so
workflow initial states no longer depend on the last document_processing run
having seen every file (a file saved by reference_downloader after that run,
say). Only supporting files with cached markdown count as processed: a file
whose conversion failed has none, and summarization / reference matching
would abort trying to read it."""

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from lib.models.file import File, FileRole
from lib.services.files import get_main_file_id, get_processed_supporting_file_ids

PROJECT_ID = uuid4()


def _file(
    role: FileRole,
    revision: int | None,
    markdown: str | None = "# md",
    project_id: UUID = PROJECT_ID,
) -> File:
    return File(
        id=uuid4(),
        project_id=project_id,
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


def _lookup(files: list[File]) -> AsyncMock:
    return AsyncMock(return_value=files)


@pytest.mark.asyncio
async def test_get_main_file_id_returns_the_revision_main_file():
    main = _file(FileRole.MAIN, revision=2)
    with patch(
        "lib.services.files.get_files_by_project_id", new=_lookup([main])
    ) as lookup:
        assert await get_main_file_id(PROJECT_ID, 2) == str(main.id)

    lookup.assert_awaited_once_with(PROJECT_ID, roles=[FileRole.MAIN], revision=2)


@pytest.mark.asyncio
async def test_get_main_file_id_ignores_a_main_row_without_a_revision():
    """The query returns shared rows (revision IS NULL) alongside the
    revision's own; a MAIN row stored that way must not be picked up."""
    stray = _file(FileRole.MAIN, revision=None)
    main = _file(FileRole.MAIN, revision=2)
    with patch(
        "lib.services.files.get_files_by_project_id", new=_lookup([stray, main])
    ):
        assert await get_main_file_id(PROJECT_ID, 2) == str(main.id)


@pytest.mark.asyncio
async def test_get_main_file_id_raises_when_the_revision_has_no_main_file():
    with patch("lib.services.files.get_files_by_project_id", new=_lookup([])):
        with pytest.raises(ValueError, match="No main file found"):
            await get_main_file_id(PROJECT_ID, 1)


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_lists_files_with_cached_markdown():
    a, b = _file(FileRole.SUPPORT, None), _file(FileRole.SUPPORT, None)
    with patch(
        "lib.services.files.get_files_by_project_id", new=_lookup([a, b])
    ) as lookup:
        assert await get_processed_supporting_file_ids(PROJECT_ID, 1) == [
            str(a.id),
            str(b.id),
        ]

    lookup.assert_awaited_once_with(PROJECT_ID, roles=[FileRole.SUPPORT], revision=1)


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_skips_files_without_cached_markdown():
    """A supporting file whose conversion failed keeps its row but has no
    markdown. It must be left out so consumers do not abort on it."""
    ok = _file(FileRole.SUPPORT, None)
    failed = _file(FileRole.SUPPORT, None, markdown=None)
    with patch("lib.services.files.get_files_by_project_id", new=_lookup([failed, ok])):
        assert await get_processed_supporting_file_ids(PROJECT_ID, 1) == [str(ok.id)]


@pytest.mark.asyncio
async def test_processed_supporting_file_ids_is_empty_without_support_files():
    with patch("lib.services.files.get_files_by_project_id", new=_lookup([])):
        assert await get_processed_supporting_file_ids(PROJECT_ID, 1) == []
