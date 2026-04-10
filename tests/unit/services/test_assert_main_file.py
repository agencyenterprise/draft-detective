"""Unit tests for assert_project_has_main_file validation."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lib.services.files import assert_project_has_main_file


def _mock_session(count: int):
    """Create a mock async DB session that returns the given count."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = count
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.mark.asyncio
async def test_raises_422_when_no_main_file():
    """Should raise HTTPException 422 when project has no MAIN file for the revision."""
    with patch(
        "lib.services.files.get_async_db_session",
        return_value=_mock_session(count=0),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await assert_project_has_main_file(str(uuid.uuid4()), revision=1)

    assert exc_info.value.status_code == 422
    assert "No main document found" in exc_info.value.detail
    assert "revision 1" in exc_info.value.detail


@pytest.mark.asyncio
async def test_raises_422_for_new_revision_without_upload():
    """After creating revision 2 but before uploading, should raise 422."""
    with patch(
        "lib.services.files.get_async_db_session",
        return_value=_mock_session(count=0),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await assert_project_has_main_file(str(uuid.uuid4()), revision=2)

    assert exc_info.value.status_code == 422
    assert "revision 2" in exc_info.value.detail


@pytest.mark.asyncio
async def test_passes_when_main_file_exists():
    """Should not raise when the project has a MAIN file for the revision."""
    with patch(
        "lib.services.files.get_async_db_session",
        return_value=_mock_session(count=1),
    ):
        await assert_project_has_main_file(str(uuid.uuid4()), revision=1)


@pytest.mark.asyncio
async def test_error_message_mentions_upload_instructions():
    """The error detail should guide the user on how to upload a document."""
    with patch(
        "lib.services.files.get_async_db_session",
        return_value=_mock_session(count=0),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await assert_project_has_main_file(str(uuid.uuid4()), revision=1)

    assert "TUS upload" in exc_info.value.detail
    assert "content_markdown" in exc_info.value.detail
