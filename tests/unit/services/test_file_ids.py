"""get_main_file_id / get_supporting_file_ids read the file table, so workflow
initial states no longer depend on the last document_processing run having
seen every file (a file saved by reference_downloader after that run, say)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from lib.models.file import File, FileRole
from lib.services.files import get_main_file_id, get_supporting_file_ids


def _file(role: FileRole, revision: int | None) -> File:
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
async def test_get_supporting_file_ids_lists_support_files_only():
    a, b = _file(FileRole.SUPPORT, None), _file(FileRole.SUPPORT, None)
    with patch(
        "lib.services.files.get_files_by_project_id",
        new=AsyncMock(return_value=[a, b]),
    ) as lookup:
        assert await get_supporting_file_ids(a.project_id, 1) == [str(a.id), str(b.id)]

    lookup.assert_awaited_once_with(a.project_id, roles=[FileRole.SUPPORT], revision=1)


@pytest.mark.asyncio
async def test_get_supporting_file_ids_is_empty_without_support_files():
    with patch(
        "lib.services.files.get_files_by_project_id", new=AsyncMock(return_value=[])
    ):
        assert await get_supporting_file_ids(uuid4(), 1) == []
