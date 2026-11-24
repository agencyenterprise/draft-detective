"""The share-link lifecycle: enabling, revoking and re-enabling a project's link.

`test_project_overview_view.py` covers reading through a link that already
exists. This file covers the write side in `lib.services.projects.share_links` and its
routes: a revoked link must stop granting access, and only the owner may turn
sharing on or off.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlmodel import col

from lib.api.routers.share import disable_project_sharing, enable_project_sharing
from lib.config.database import get_async_db_session
from lib.config.env import config
from lib.models.project import FeedbackVisibility, Project
from lib.models.share_link import ShareLink
from lib.models.user import User, UserRole
from lib.services.projects.service import delete_project, get_project_access
from lib.services.projects.share_links import (
    ShareStatusResponse,
    disable_sharing,
    enable_sharing,
    get_resource_by_token,
    get_share_status,
)

ShareRoute = Callable[..., Awaitable[ShareStatusResponse]]


def _user(label: str, role: UserRole = UserRole.USER) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"share-links-{label}-{uuid.uuid4()}@example.com",
        name=label,
        role=role,
        show_experimental_features=False,
    )


@pytest_asyncio.fixture
async def setup() -> AsyncIterator[dict[str, Any]]:
    """Two projects of one owner, a stranger, and an admin who may read both."""
    owner, stranger = _user("owner"), _user("stranger")
    admin = _user("admin", UserRole.ADMIN)
    projects = [
        Project(
            id=uuid.uuid4(),
            user_id=owner.id,
            title=f"share-links {i}",
            feedback_visibility=FeedbackVisibility.FULL_PROJECT,
        )
        for i in range(2)
    ]
    users = [owner, stranger, admin]
    async with get_async_db_session() as session:
        session.add_all(users)
        await session.commit()
    async with get_async_db_session() as session:
        session.add_all(projects)
        await session.commit()

    yield {
        "owner": owner,
        "stranger": stranger,
        "admin": admin,
        "project": projects[0],
        "other_project": projects[1],
    }

    project_ids = [p.id for p in projects]
    async with get_async_db_session() as session:
        await session.execute(
            delete(ShareLink).where(col(ShareLink.project_id).in_(project_ids))
        )
        await session.execute(delete(Project).where(col(Project.id).in_(project_ids)))
        await session.execute(
            delete(User).where(col(User.id).in_([u.id for u in users]))
        )
        await session.commit()


async def _links(project: Project) -> list[ShareLink]:
    async with get_async_db_session() as session:
        stmt = select(ShareLink).where(col(ShareLink.project_id) == project.id)
        return list((await session.execute(stmt)).scalars().all())


async def _enabled_token(project: Project, owner: User) -> str:
    status = await enable_sharing(project.id, owner)
    assert status.share_link is not None
    return status.share_link.token


async def _reads_with_token(project: Project, token: str) -> bool:
    try:
        await get_project_access(str(project.id), share_token=token)
    except HTTPException as exc:
        assert exc.status_code == 403
        return False
    return True


@pytest.mark.asyncio
async def test_enabling_creates_one_active_link_with_a_frontend_url(
    setup: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "FRONTEND_URL", "https://dd.example")
    project = setup["project"]

    status = await enable_sharing(project.id, setup["owner"])

    assert status.enabled is True
    assert status.share_link is not None
    token = status.share_link.token
    assert status.share_link.url == f"https://dd.example/share/{token}"
    [link] = await _links(project)
    assert (link.token, link.is_active) == (token, True)
    assert link.created_by_user_id == setup["owner"].id
    assert await get_share_status(project.id) == status


@pytest.mark.asyncio
async def test_enabling_twice_returns_the_same_link(setup: dict[str, Any]) -> None:
    project, owner = setup["project"], setup["owner"]

    first = await _enabled_token(project, owner)
    second = await _enabled_token(project, owner)

    assert first == second
    assert len(await _links(project)) == 1


@pytest.mark.asyncio
async def test_disabling_revokes_access_through_the_link(setup: dict[str, Any]) -> None:
    project = setup["project"]
    token = await _enabled_token(project, setup["owner"])
    assert await _reads_with_token(project, token)

    status = await disable_sharing(project.id)

    assert (status.enabled, status.share_link) == (False, None)
    assert await get_resource_by_token(token) is None
    assert not await _reads_with_token(project, token)
    assert (await get_share_status(project.id)).enabled is False


@pytest.mark.asyncio
async def test_re_enabling_issues_a_new_token_and_the_old_one_stays_dead(
    setup: dict[str, Any],
) -> None:
    project, owner = setup["project"], setup["owner"]
    old = await _enabled_token(project, owner)
    await disable_sharing(project.id)

    new = await _enabled_token(project, owner)

    assert new != old
    assert await _reads_with_token(project, new)
    assert not await _reads_with_token(project, old)


@pytest.mark.asyncio
async def test_disabling_revokes_every_active_link_of_the_resource_only(
    setup: dict[str, Any],
) -> None:
    project, other, owner = setup["project"], setup["other_project"], setup["owner"]
    # Two active links for one project: the orphaned state disable must clean up.
    orphans = [
        ShareLink(project_id=project.id, created_by_user_id=owner.id) for _ in range(2)
    ]
    async with get_async_db_session() as session:
        session.add_all(orphans)
        await session.commit()
    other_token = await _enabled_token(other, owner)

    await disable_sharing(project.id)

    assert [link.is_active for link in await _links(project)] == [False, False]
    assert await _reads_with_token(other, other_token)


@pytest.mark.asyncio
async def test_a_link_reads_only_its_own_project(setup: dict[str, Any]) -> None:
    token = await _enabled_token(setup["project"], setup["owner"])

    assert not await _reads_with_token(setup["other_project"], token)


@pytest.mark.asyncio
async def test_disabling_a_project_that_was_never_shared_is_a_no_op(
    setup: dict[str, Any],
) -> None:
    status = await disable_sharing(setup["project"].id)

    assert (status.enabled, status.share_link) == (False, None)
    assert await _links(setup["project"]) == []


@pytest.mark.asyncio
async def test_owner_toggles_sharing_through_the_routes(setup: dict[str, Any]) -> None:
    project, owner = setup["project"], setup["owner"]

    enabled = await enable_project_sharing(str(project.id), current_user=owner)
    disabled = await disable_project_sharing(str(project.id), current_user=owner)

    assert enabled.enabled is True
    assert disabled.enabled is False
    assert [link.is_active for link in await _links(project)] == [False]


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["stranger", "admin"])
@pytest.mark.parametrize("route", [enable_project_sharing, disable_project_sharing])
async def test_only_the_owner_may_toggle_sharing(
    setup: dict[str, Any], who: str, route: ShareRoute
) -> None:
    project, owner = setup["project"], setup["owner"]
    token = await _enabled_token(project, owner)

    with pytest.raises(HTTPException) as exc:
        await route(str(project.id), current_user=setup[who])

    assert exc.value.status_code == 403
    # The owner's link is untouched: not revoked, and no second one created.
    [link] = await _links(project)
    assert (link.token, link.is_active) == (token, True)


@pytest.mark.asyncio
async def test_deleting_a_project_removes_its_share_links_only(
    setup: dict[str, Any],
) -> None:
    project, other, owner = setup["project"], setup["other_project"], setup["owner"]
    token = await _enabled_token(project, owner)
    other_token = await _enabled_token(other, owner)

    await delete_project(str(project.id), user=owner)

    assert await _links(project) == []
    assert await get_resource_by_token(token) is None
    assert await _reads_with_token(other, other_token)
