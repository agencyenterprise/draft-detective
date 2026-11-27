"""The DOCX export's error responses: a reason the caller can act on, and
nothing about the server's own files."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from lib.api.routers.projects import download_project_docx
from lib.models.project import Project
from lib.services.docx.service import UnsupportedMainFileError, generate_docx
from lib.services.file_artifacts_service.file_artifacts_service import (
    MainFileNotFoundError,
)


async def _export_error(
    generate: AsyncMock, revision: int | None = None
) -> HTTPException:
    with (
        patch("lib.api.routers.projects.get_project_access", AsyncMock()),
        patch("lib.api.routers.projects.generate_docx", generate),
        pytest.raises(HTTPException) as caught,
    ):
        await download_project_docx(
            project_id=str(uuid.uuid4()),
            share_token=None,
            severities=None,
            workflow_types=None,
            docx_type="original",
            include_passing=False,
            include_edits=True,
            revision=revision,
            current_user=None,
        )
    return caught.value


@pytest.mark.asyncio
async def test_failure_hides_the_server_path():
    """A stored upload gone from disk: the 500 must not name where it was."""
    path = "/app/uploads/1234/report.docx"
    error = await _export_error(
        AsyncMock(side_effect=FileNotFoundError(f"Original file not found: {path}"))
    )

    assert error.status_code == 500
    assert error.detail == "Failed to generate DOCX"


@pytest.mark.asyncio
async def test_library_value_error_is_a_server_failure_not_a_bad_request():
    """A ValueError from inside the DOCX code is ours, not the caller's."""
    error = await _export_error(
        AsyncMock(
            side_effect=ValueError("file '/app/uploads/1234/report.docx' is not a zip")
        )
    )

    assert error.status_code == 500
    assert error.detail == "Failed to generate DOCX"


@pytest.mark.asyncio
async def test_unknown_revision_is_still_a_bad_request_with_its_reason():
    """The frontend shows a 4xx reason to the user, so its wording stays."""
    project = Project(id=uuid.uuid4(), title="Report", current_revision=2)
    with patch(
        "lib.services.docx.service.get_project_by_id", AsyncMock(return_value=project)
    ):
        error = await _export_error(AsyncMock(wraps=generate_docx), revision=5)

    assert error.status_code == 400
    assert error.detail == (
        "Revision 5 does not exist for this project (it has revisions 1 to 2)"
    )


@pytest.mark.asyncio
async def test_non_word_main_file_is_still_a_bad_request_with_its_reason():
    message = "Main file must be a .docx or .doc to generate reviewed DOCX"
    error = await _export_error(
        AsyncMock(side_effect=UnsupportedMainFileError(message))
    )

    assert error.status_code == 400
    assert error.detail == message


@pytest.mark.asyncio
async def test_revision_without_a_main_document_is_still_a_bad_request():
    """A revision created but not yet uploaded to: the caller's state, not ours."""
    message = "No main file found for revision 2 in project p1"
    error = await _export_error(AsyncMock(side_effect=MainFileNotFoundError(message)))

    assert error.status_code == 400
    assert error.detail == message
