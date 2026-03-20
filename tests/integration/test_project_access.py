"""Integration tests for get_project_access — the central project permission gate."""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import AccessLevel, FeedbackVisibility, Project
from lib.models.share_link import ShareLink, generate_share_token
from lib.models.user import User, UserRole
from lib.services.projects import get_project_access


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def owner():
    user = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4()}@example.com",
        name="Owner",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    yield user
    async with get_async_db_session() as session:
        u = (await session.execute(select(User).where(col(User.id) == user.id))).scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


@pytest_asyncio.fixture
async def admin():
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4()}@example.com",
        name="Admin",
        role=UserRole.ADMIN,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    yield user
    async with get_async_db_session() as session:
        u = (await session.execute(select(User).where(col(User.id) == user.id))).scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


@pytest_asyncio.fixture
async def other_user():
    user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4()}@example.com",
        name="Other",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    yield user
    async with get_async_db_session() as session:
        u = (await session.execute(select(User).where(col(User.id) == user.id))).scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


async def _make_project(owner: User, visibility: FeedbackVisibility | None) -> Project:
    project = Project(
        id=uuid.uuid4(),
        title="Test Project",
        user_id=owner.id,
        feedback_visibility=visibility,
    )
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()
    return project


async def _delete_project(project: Project) -> None:
    async with get_async_db_session() as session:
        p = (await session.execute(select(Project).where(col(Project.id) == project.id))).scalar_one_or_none()
        if p:
            await session.delete(p)
            await session.commit()


async def _make_share_link(project: Project, owner: User) -> ShareLink:
    link = ShareLink(
        id=uuid.uuid4(),
        token=generate_share_token(),
        resource_type="project",
        resource_id=project.id,
        created_by_user_id=owner.id,
        is_active=True,
    )
    async with get_async_db_session() as session:
        session.add(link)
        await session.commit()
    return link


async def _delete_share_link(link: ShareLink) -> None:
    async with get_async_db_session() as session:
        s = (await session.execute(select(ShareLink).where(col(ShareLink.id) == link.id))).scalar_one_or_none()
        if s:
            await session.delete(s)
            await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_gets_write_access(owner):
    project = await _make_project(owner, FeedbackVisibility.PRIVATE)
    try:
        result_project, level = await get_project_access(str(project.id), user=owner)
        assert level == AccessLevel.WRITE
        assert result_project.id == project.id
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_non_owner_user_is_denied(owner, other_user):
    project = await _make_project(owner, FeedbackVisibility.FULL_PROJECT)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id), user=other_user)
        assert exc_info.value.status_code == 403
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_admin_with_full_project_visibility_gets_read_access(owner, admin):
    project = await _make_project(owner, FeedbackVisibility.FULL_PROJECT)
    try:
        result_project, level = await get_project_access(str(project.id), user=admin)
        assert level == AccessLevel.READ
        assert result_project.id == project.id
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", [FeedbackVisibility.PRIVATE, FeedbackVisibility.ISSUE_ONLY])
async def test_admin_without_full_project_visibility_is_denied(owner, admin, visibility):
    project = await _make_project(owner, visibility)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id), user=admin)
        assert exc_info.value.status_code == 403
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_valid_share_token_grants_read_access(owner):
    project = await _make_project(owner, FeedbackVisibility.PRIVATE)
    link = await _make_share_link(project, owner)
    try:
        result_project, level = await get_project_access(str(project.id), share_token=link.token)
        assert level == AccessLevel.READ
        assert result_project.id == project.id
    finally:
        await _delete_share_link(link)
        await _delete_project(project)


@pytest.mark.asyncio
async def test_invalid_share_token_is_denied(owner):
    project = await _make_project(owner, FeedbackVisibility.PRIVATE)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id), share_token="not-a-real-token")
        assert exc_info.value.status_code == 403
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_share_token_denied_when_write_required(owner):
    project = await _make_project(owner, FeedbackVisibility.PRIVATE)
    link = await _make_share_link(project, owner)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id), share_token=link.token, required_level=AccessLevel.WRITE)
        assert exc_info.value.status_code == 403
        assert "Write access required" in exc_info.value.detail
    finally:
        await _delete_share_link(link)
        await _delete_project(project)


@pytest.mark.asyncio
async def test_admin_with_full_project_denied_when_write_required(owner, admin):
    project = await _make_project(owner, FeedbackVisibility.FULL_PROJECT)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id), user=admin, required_level=AccessLevel.WRITE)
        assert exc_info.value.status_code == 403
        assert "Write access required" in exc_info.value.detail
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_no_credentials_is_denied(owner):
    project = await _make_project(owner, FeedbackVisibility.FULL_PROJECT)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_project_access(str(project.id))
        assert exc_info.value.status_code == 403
    finally:
        await _delete_project(project)


@pytest.mark.asyncio
async def test_nonexistent_project_raises_404(owner):
    with pytest.raises(HTTPException) as exc_info:
        await get_project_access(str(uuid.uuid4()), user=owner)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_uuid_raises_404(owner):
    with pytest.raises(HTTPException) as exc_info:
        await get_project_access("not-a-valid-uuid", user=owner)
    assert exc_info.value.status_code == 404
