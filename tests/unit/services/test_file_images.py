"""Unit tests for `lib.services.files.images`."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.sql.dml import Delete

from lib.models.file import FileRole
from lib.services.files.images import replace_extracted_images
from lib.services.image_extraction import ExtractedImage

MODULE = "lib.services.files.images"


class _FakeSession:
    def __init__(self, previous_rows: list | None = None):
        self.previous_rows = previous_rows or []
        self.executed: list = []
        self.added: list = []
        self.committed = False

    async def execute(self, stmt):
        self.executed.append(stmt)
        if not isinstance(stmt, Delete):
            result = SimpleNamespace(scalars=lambda: iter(self.previous_rows))
            return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _parent() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        revision=3,
    )


def _extracted(alt: str = "") -> ExtractedImage:
    return ExtractedImage(
        image_path="/uploads/extracted_images/abc.png",
        mime_type="image/png",
        file_size=123,
        content_hash="abc",
        line_number=7,
        alt=alt,
    )


@pytest.mark.asyncio
async def test_replaces_rows_and_inherits_parent_fields():
    parent = _parent()
    session = _FakeSession()
    images = [_extracted(alt="Figure 1"), _extracted()]

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
    ):
        await replace_extracted_images(parent.id, images)

    # Old rows for this parent are deleted before the new ones go in, so a
    # reconversion never leaves stale images behind.
    deletes = [s for s in session.executed if isinstance(s, Delete)]
    assert len(deletes) == 1
    assert "parent_file_id" in str(deletes[0])

    assert [f.id for f in session.added] == [images[0].id, images[1].id]
    assert [f.file_name for f in session.added] == ["image-1.png", "image-2.png"]
    for row in session.added:
        assert row.role == FileRole.EXTRACTED_IMAGE
        assert row.parent_file_id == parent.id
        assert row.project_id == parent.project_id
        assert row.uploaded_by == parent.uploaded_by
        assert row.revision == parent.revision
        assert row.file_path == "/uploads/extracted_images/abc.png"
        assert row.file_type == "image/png"
        assert row.content_hash == "abc"
    # Alt text lands in description; empty alt stays NULL.
    assert [f.description for f in session.added] == ["Figure 1", None]
    assert session.committed


@pytest.mark.asyncio
async def test_no_images_still_clears_previous_rows():
    parent = _parent()
    session = _FakeSession()

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
    ):
        await replace_extracted_images(parent.id, [])

    assert any(isinstance(s, Delete) for s in session.executed)
    assert session.added == []
    assert session.committed


def _previous_row(path: str) -> SimpleNamespace:
    return SimpleNamespace(file_path=path, id=uuid.uuid4())


@pytest.mark.asyncio
async def test_stale_disk_file_of_replaced_row_is_removed():
    """A reconversion that produced different bytes must not strand the old
    files on disk — cleanup discovers disk files only through rows."""
    parent = _parent()
    session = _FakeSession(
        previous_rows=[_previous_row("/uploads/extracted_images/old.png")]
    )

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
        patch(f"{MODULE}._is_path_shared", new=AsyncMock(return_value=False)),
        patch(f"{MODULE}._delete_file_from_disk") as disk_mock,
    ):
        await replace_extracted_images(parent.id, [_extracted()])

    disk_mock.assert_called_once_with("/uploads/extracted_images/old.png")


@pytest.mark.asyncio
async def test_disk_file_reused_by_new_images_is_kept():
    """Same-bytes reconversion reuses content-addressed paths; the new rows
    are not inserted yet when the old ones are checked."""
    parent = _parent()
    image = _extracted()
    session = _FakeSession(previous_rows=[_previous_row(image.image_path)])

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
        patch(f"{MODULE}._is_path_shared", new=AsyncMock(return_value=False)),
        patch(f"{MODULE}._delete_file_from_disk") as disk_mock,
    ):
        await replace_extracted_images(parent.id, [image])

    disk_mock.assert_not_called()


@pytest.mark.asyncio
async def test_disk_file_shared_with_another_row_is_kept():
    parent = _parent()
    session = _FakeSession(
        previous_rows=[_previous_row("/uploads/extracted_images/shared.png")]
    )

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
        patch(f"{MODULE}._is_path_shared", new=AsyncMock(return_value=True)),
        patch(f"{MODULE}._delete_file_from_disk") as disk_mock,
    ):
        await replace_extracted_images(parent.id, [_extracted()])

    disk_mock.assert_not_called()


@pytest.mark.asyncio
async def test_disk_cleanup_happens_only_after_commit():
    """A failed transaction restores the old rows; their files must still
    exist, so deletion may only run once the commit has succeeded."""
    parent = _parent()
    events: list = []

    session = _FakeSession(
        previous_rows=[_previous_row("/uploads/extracted_images/old.png")]
    )
    original_commit = session.commit

    async def logging_commit():
        events.append("commit")
        await original_commit()

    session.commit = logging_commit

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
        patch(f"{MODULE}._is_path_shared", new=AsyncMock(return_value=False)),
        patch(
            f"{MODULE}._delete_file_from_disk",
            side_effect=lambda path: events.append(f"disk:{path}"),
        ),
    ):
        await replace_extracted_images(parent.id, [_extracted()])

    assert events == ["commit", "disk:/uploads/extracted_images/old.png"]


@pytest.mark.asyncio
async def test_no_disk_cleanup_when_commit_fails():
    parent = _parent()
    session = _FakeSession(
        previous_rows=[_previous_row("/uploads/extracted_images/old.png")]
    )

    async def failing_commit():
        raise RuntimeError("constraint violation")

    session.commit = failing_commit

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=parent)),
        patch(f"{MODULE}.get_async_db_session", return_value=session),
        patch(f"{MODULE}._is_path_shared", new=AsyncMock(return_value=False)),
        patch(f"{MODULE}._delete_file_from_disk") as disk_mock,
        pytest.raises(RuntimeError),
    ):
        await replace_extracted_images(parent.id, [_extracted()])

    disk_mock.assert_not_called()
