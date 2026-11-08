"""Every reader of a project's uploaded documents sees the same roles.

One file per role, so a reader that drifts from the others shows up as a file
missing from (or leaking into) its list. A new role left out of
UPLOADED_ROLES is not caught here: every reader leaves it out alike.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.files.service import get_project_files_list_items
from lib.services.projects.service import get_project_files
from lib.services.review_assistant_requests import assert_project_files

UPLOADED = {
    FileRole.MAIN,
    FileRole.SUPPORT,
    FileRole.REVIEWER_MEMO,
    FileRole.RESPONSE_MEMO,
    FileRole.REVIEW_INPUT,
}


@pytest_asyncio.fixture
async def files_by_role() -> AsyncIterator[tuple[Project, dict[FileRole, File]]]:
    """A project holding one file of every role."""
    user = User(
        id=uuid.uuid4(),
        email=f"roles-{uuid.uuid4()}@example.com",
        name="Roles Tester",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(id=uuid.uuid4(), title="Roles", user_id=user.id)
    files = {
        role: File(
            id=uuid.uuid4(),
            project_id=project.id,
            file_name=f"{role.value}.pdf",
            file_path=f"path/{role.value}.pdf",
            file_type="application/pdf",
            file_size=1234,
            content_hash=str(uuid.uuid4()),
            role=role,
            uploaded_by=user.id,
            revision=1 if role == FileRole.MAIN else None,
            markdown=f"# {role.value}",
        )
        for role in FileRole
    }
    # Commit in dependency order (users → projects → files) to satisfy FKs.
    for rows in ([user], [project], list(files.values())):
        async with get_async_db_session() as session:
            session.add_all(rows)
            await session.commit()

    yield project, files

    async with get_async_db_session() as session:
        await session.execute(delete(File).where(col(File.project_id) == project.id))
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


@pytest.mark.asyncio
async def test_project_file_lists_hold_every_uploaded_role(files_by_role) -> None:
    project, _ = files_by_role

    full = await get_project_files(str(project.id))
    items = await get_project_files_list_items(project.id)

    assert {f.role for f in full} == UPLOADED
    assert {i.role for i in items} == UPLOADED


@pytest.mark.asyncio
async def test_review_assistant_accepts_only_uploaded_roles(files_by_role) -> None:
    project, files = files_by_role
    uploaded_ids = [str(files[role].id) for role in UPLOADED]

    await assert_project_files(str(project.id), uploaded_ids)

    for role in set(FileRole) - UPLOADED:
        with pytest.raises(HTTPException) as raised:
            await assert_project_files(str(project.id), [str(files[role].id)])
        assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_file_documents_load_only_uploaded_roles(files_by_role) -> None:
    project, files = files_by_role
    service = FileArtifactsService(str(project.id), revision=1)

    loaded = await service.get_file_documents([str(f.id) for f in files.values()])

    by_id = {str(f.id): role for role, f in files.items()}
    assert {by_id[d.file_id] for d in loaded.documents} == UPLOADED
    assert {by_id[u.file_id] for u in loaded.unreadable} == set(FileRole) - UPLOADED
