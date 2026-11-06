"""The TUS completion hook's one-main-per-revision guard.

A main upload is refused when its revision already has a main document, and
allowed otherwise. A shared row (revision IS NULL) is not the revision's main
document, so it never blocks an upload.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from lib.api.routers.tus_upload import _get_completion_hook
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User
from tests.unit.services.files.fake_file_query import file_row, patched_file_query

MODULE = "lib.api.routers.tus_upload"
PROJECT_ID = uuid.uuid4()


def _project() -> Project:
    return Project(
        id=PROJECT_ID, title="Test", user_id=uuid.uuid4(), current_revision=2
    )


async def _upload_main(rows: list[File]) -> AsyncMock:
    """Complete a main upload against these rows; return the finalize mock."""
    finalize = AsyncMock(return_value=(file_row(PROJECT_ID, FileRole.MAIN, 2), False))
    user = User(id=uuid.uuid4(), email="u@example.com")
    handler = _get_completion_hook(current_user=user)
    with (
        patched_file_query(rows, MODULE),
        patch(
            f"{MODULE}.get_project_access",
            AsyncMock(return_value=(_project(), None)),
        ),
        patch(f"{MODULE}.finalize_file_from_path", finalize),
    ):
        await handler(
            "/nonexistent/upload",
            {"project_id": str(PROJECT_ID), "role": "main", "filename": "d.docx"},
        )
    return finalize


@pytest.mark.asyncio
async def test_refuses_a_second_main_for_the_revision() -> None:
    rows = [file_row(PROJECT_ID, FileRole.MAIN, 2)]
    with pytest.raises(HTTPException) as exc:
        await _upload_main(rows)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_allows_a_main_when_only_earlier_revisions_have_one() -> None:
    rows = [
        file_row(PROJECT_ID, FileRole.MAIN, 1),
        file_row(PROJECT_ID, FileRole.SUPPORT, None),
    ]
    finalize = await _upload_main(rows)
    assert finalize.await_args is not None
    assert finalize.await_args.kwargs["revision"] == 2


@pytest.mark.asyncio
async def test_a_shared_main_row_does_not_block_the_upload() -> None:
    rows = [file_row(PROJECT_ID, FileRole.MAIN, None)]
    finalize = await _upload_main(rows)
    finalize.assert_awaited_once()
