"""Unit tests for create_file_record's unique-constraint handling.

Two concurrent MAIN uploads can both pass the application-level
one-main-per-revision check; the partial unique index is the backstop, and its
IntegrityError must surface as a 409 rather than a 500.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from lib.models.file import FileRole
from lib.services.files.service import create_file_record


class _FakeSession:
    """Async session stub whose commit raises a configurable error."""

    def __init__(self, commit_error: Exception | None = None):
        self._commit_error = commit_error

    def add(self, obj):
        pass

    async def commit(self):
        if self._commit_error is not None:
            raise self._commit_error

    async def refresh(self, obj):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _integrity_error(message: str) -> IntegrityError:
    return IntegrityError(statement="INSERT ...", params=None, orig=Exception(message))


async def _create_record(session: _FakeSession):
    with patch(
        "lib.services.files.service.get_async_db_session",
        side_effect=lambda: session,
    ):
        return await create_file_record(
            project_id=uuid.uuid4(),
            file_name="document.pdf",
            file_path="/uploads/abc123.pdf",
            file_type="application/pdf",
            file_size=123,
            content_hash="abc123",
            role=FileRole.MAIN,
            uploaded_by=uuid.uuid4(),
            revision=1,
        )


@pytest.mark.asyncio
async def test_main_per_revision_violation_becomes_409():
    session = _FakeSession(
        commit_error=_integrity_error(
            "duplicate key value violates unique constraint "
            '"uq_files_one_main_per_project_revision"'
        )
    )

    with pytest.raises(HTTPException) as exc:
        await _create_record(session)

    assert exc.value.status_code == 409
    assert "main document" in exc.value.detail


@pytest.mark.asyncio
async def test_unrelated_integrity_error_is_reraised():
    session = _FakeSession(
        commit_error=_integrity_error(
            'insert or update on table "files" violates foreign key constraint '
            '"files_project_id_fkey"'
        )
    )

    with pytest.raises(IntegrityError):
        await _create_record(session)


@pytest.mark.asyncio
async def test_successful_commit_returns_the_record():
    record = await _create_record(_FakeSession())

    assert record.file_name == "document.pdf"
    assert record.role == FileRole.MAIN
    assert record.revision == 1
