"""Integration tests for the file download's access checks.

A file is readable by whoever can read its project, so these follow the cases of
`test_project_access.py` through a file of the project.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.models.project import FeedbackVisibility, Project
from lib.models.share_link import ShareLink, generate_share_token
from lib.models.user import User, UserRole
from lib.services.files.access import (
    check_file_access,
    check_file_access_by_share_token,
)


async def _persisted_user(label: str, role: UserRole) -> AsyncIterator[User]:
    user = User(
        id=uuid.uuid4(),
        email=f"{label}-{uuid.uuid4()}@example.com",
        name=label.title(),
        role=role,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    yield user
    async with get_async_db_session() as session:
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


@pytest_asyncio.fixture
async def owner() -> AsyncIterator[User]:
    async for user in _persisted_user("owner", UserRole.USER):
        yield user


@pytest_asyncio.fixture
async def admin() -> AsyncIterator[User]:
    async for user in _persisted_user("admin", UserRole.ADMIN):
        yield user


@pytest_asyncio.fixture
async def stranger() -> AsyncIterator[User]:
    async for user in _persisted_user("stranger", UserRole.USER):
        yield user


class _Project:
    """A project of the owner's with one file and an active share link."""

    def __init__(self, owner: User, visibility: FeedbackVisibility) -> None:
        self.project = Project(
            id=uuid.uuid4(),
            title="File access",
            user_id=owner.id,
            feedback_visibility=visibility,
        )
        self.file = File(
            id=uuid.uuid4(),
            project_id=self.project.id,
            file_name="report.pdf",
            file_path="/nowhere/report.pdf",
            file_type="application/pdf",
            file_size=1,
            content_hash=f"hash-{uuid.uuid4()}",
            role=FileRole.MAIN,
            uploaded_by=owner.id,
        )
        self.link = ShareLink(
            id=uuid.uuid4(),
            token=generate_share_token(),
            resource_type="project",
            resource_id=self.project.id,
            created_by_user_id=owner.id,
            is_active=True,
        )

    async def save(self) -> None:
        async with get_async_db_session() as session:
            session.add(self.project)
            await session.flush()
            session.add_all([self.file, self.link])
            await session.commit()

    async def deactivate_link(self) -> None:
        async with get_async_db_session() as session:
            link = await session.get(ShareLink, self.link.id)
            assert link is not None
            link.is_active = False
            await session.commit()

    async def remove(self) -> None:
        async with get_async_db_session() as session:
            await session.execute(
                delete(ShareLink).where(col(ShareLink.id) == self.link.id)
            )
            await session.execute(delete(File).where(col(File.id) == self.file.id))
            await session.execute(
                delete(Project).where(col(Project.id) == self.project.id)
            )
            await session.commit()


async def _project(
    owner: User, visibility: FeedbackVisibility = FeedbackVisibility.PRIVATE
) -> AsyncIterator[_Project]:
    project = _Project(owner, visibility)
    await project.save()
    yield project
    await project.remove()


@pytest_asyncio.fixture
async def private(owner: User) -> AsyncIterator[_Project]:
    async for project in _project(owner):
        yield project


@pytest_asyncio.fixture
async def shared_with_admins(owner: User) -> AsyncIterator[_Project]:
    async for project in _project(owner, FeedbackVisibility.FULL_PROJECT):
        yield project


@pytest_asyncio.fixture
async def other(owner: User) -> AsyncIterator[_Project]:
    async for project in _project(owner):
        yield project


async def _status(call: Awaitable[File]) -> int:
    with pytest.raises(HTTPException) as refused:
        await call
    return refused.value.status_code


@pytest.mark.asyncio
async def test_the_owner_reads_the_file(owner: User, private: _Project) -> None:
    file = await check_file_access(private.file.id, owner)

    assert file.id == private.file.id


@pytest.mark.asyncio
async def test_a_signed_in_stranger_is_refused(
    stranger: User, shared_with_admins: _Project
) -> None:
    assert await _status(check_file_access(shared_with_admins.file.id, stranger)) == 403


@pytest.mark.asyncio
async def test_an_admin_reads_a_project_shared_with_admins(
    admin: User, shared_with_admins: _Project
) -> None:
    """The admin who can open the project can open its files and document images."""
    file = await check_file_access(shared_with_admins.file.id, admin)

    assert file.id == shared_with_admins.file.id


@pytest.mark.asyncio
async def test_an_admin_is_refused_a_private_project(
    admin: User, private: _Project
) -> None:
    assert await _status(check_file_access(private.file.id, admin)) == 403


@pytest.mark.asyncio
async def test_the_projects_share_token_reads_the_file(private: _Project) -> None:
    file = await check_file_access_by_share_token(private.file.id, private.link.token)

    assert file.id == private.file.id


@pytest.mark.asyncio
async def test_a_deactivated_share_token_is_refused(private: _Project) -> None:
    await private.deactivate_link()

    refused = check_file_access_by_share_token(private.file.id, private.link.token)
    assert await _status(refused) == 403


@pytest.mark.asyncio
async def test_another_projects_share_token_is_refused(
    private: _Project, other: _Project
) -> None:
    refused = check_file_access_by_share_token(private.file.id, other.link.token)
    assert await _status(refused) == 403


@pytest.mark.asyncio
async def test_an_unknown_file_is_404(owner: User, private: _Project) -> None:
    assert await _status(check_file_access(uuid.uuid4(), owner)) == 404
    refused = check_file_access_by_share_token(uuid.uuid4(), private.link.token)
    assert await _status(refused) == 404


@pytest.mark.asyncio
async def test_a_malformed_file_id_is_400(owner: User) -> None:
    assert await _status(check_file_access("not-a-uuid", owner)) == 400
