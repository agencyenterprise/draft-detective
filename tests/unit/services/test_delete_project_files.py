"""Unit tests for delete_project_files service function."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.files import delete_project_files


def _make_file(
    file_path: str, original_file_path: str | None = None, file_id: uuid.UUID | None = None
) -> MagicMock:
    file = MagicMock()
    file.id = file_id or uuid.uuid4()
    file.file_path = file_path
    file.original_file_path = original_file_path
    return file


class _FakeSession:
    def __init__(self, files: list):
        self._files = files
        self.deleted: list = []
        self.committed = False

    async def execute(self, _stmt):
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = self._files
        result.scalars.return_value = scalars
        return result

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _patch_session(session: _FakeSession):
    return patch("lib.services.files.get_async_db_session", return_value=session)


@pytest.mark.asyncio
async def test_returns_zero_when_project_has_no_files():
    session = _FakeSession(files=[])

    with _patch_session(session):
        count = await delete_project_files(uuid.uuid4())

    assert count == 0
    assert session.deleted == []
    assert session.committed


@pytest.mark.asyncio
async def test_deletes_all_files_when_no_target_ids():
    f1 = _make_file("/tmp/a.pdf")
    f2 = _make_file("/tmp/b.pdf")
    session = _FakeSession(files=[f1, f2])

    with (
        _patch_session(session),
        patch(
            "lib.services.files._is_path_shared", new=AsyncMock(return_value=False)
        ),
        patch("lib.services.files._delete_file_from_disk") as disk_mock,
    ):
        count = await delete_project_files(uuid.uuid4())

    assert count == 2
    assert session.deleted == [f1, f2]
    assert disk_mock.call_args_list[0].args[0] == "/tmp/a.pdf"
    assert disk_mock.call_args_list[1].args[0] == "/tmp/b.pdf"


@pytest.mark.asyncio
async def test_only_deletes_files_matching_target_ids():
    keep = _make_file("/tmp/keep.pdf")
    drop = _make_file("/tmp/drop.pdf")
    session = _FakeSession(files=[keep, drop])

    with (
        _patch_session(session),
        patch(
            "lib.services.files._is_path_shared", new=AsyncMock(return_value=False)
        ),
        patch("lib.services.files._delete_file_from_disk") as disk_mock,
    ):
        count = await delete_project_files(
            uuid.uuid4(), target_file_ids=[str(drop.id)]
        )

    assert count == 1
    assert session.deleted == [drop]
    disk_mock.assert_called_once_with("/tmp/drop.pdf")


@pytest.mark.asyncio
async def test_skips_disk_delete_for_shared_paths():
    shared = _make_file("/tmp/shared.pdf")
    session = _FakeSession(files=[shared])

    with (
        _patch_session(session),
        patch(
            "lib.services.files._is_path_shared", new=AsyncMock(return_value=True)
        ),
        patch("lib.services.files._delete_file_from_disk") as disk_mock,
    ):
        count = await delete_project_files(uuid.uuid4())

    assert count == 1
    assert session.deleted == [shared]
    disk_mock.assert_not_called()


@pytest.mark.asyncio
async def test_deletes_both_file_path_and_original_file_path():
    f = _make_file("/tmp/converted.md", original_file_path="/tmp/original.docx")
    session = _FakeSession(files=[f])

    with (
        _patch_session(session),
        patch(
            "lib.services.files._is_path_shared", new=AsyncMock(return_value=False)
        ),
        patch("lib.services.files._delete_file_from_disk") as disk_mock,
    ):
        count = await delete_project_files(uuid.uuid4())

    assert count == 1
    paths = [c.args[0] for c in disk_mock.call_args_list]
    assert paths == ["/tmp/converted.md", "/tmp/original.docx"]


@pytest.mark.asyncio
async def test_handles_missing_original_file_path():
    f = _make_file("/tmp/a.pdf", original_file_path=None)
    session = _FakeSession(files=[f])

    with (
        _patch_session(session),
        patch(
            "lib.services.files._is_path_shared", new=AsyncMock(return_value=False)
        ),
        patch("lib.services.files._delete_file_from_disk") as disk_mock,
    ):
        count = await delete_project_files(uuid.uuid4())

    assert count == 1
    disk_mock.assert_called_once_with("/tmp/a.pdf")


@pytest.mark.asyncio
async def test_accepts_project_id_as_string():
    session = _FakeSession(files=[])
    project_id = str(uuid.uuid4())

    with _patch_session(session):
        count = await delete_project_files(project_id)

    assert count == 0
