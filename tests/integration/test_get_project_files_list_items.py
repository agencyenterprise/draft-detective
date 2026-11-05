"""Integration tests for get_project_files_list_items (returns all revisions)."""

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlmodel import col

from lib.config.database import async_engine, get_async_db_session
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.services.files.service import get_project_files_list_items


@pytest_asyncio.fixture
async def project_with_revisions():
    """A project at revision 2 with a main file per revision plus a shared support file."""
    user = User(
        id=uuid.uuid4(),
        email=f"files-{uuid.uuid4()}@example.com",
        name="Files Tester",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(
        id=uuid.uuid4(), title="Revisions", user_id=user.id, current_revision=2
    )

    def _file(name: str, role: FileRole, revision: int | None) -> File:
        return File(
            id=uuid.uuid4(),
            project_id=project.id,
            file_name=name,
            file_path=f"path/{name}",
            file_type="application/pdf",
            file_size=1234,
            content_hash=str(uuid.uuid4()),
            role=role,
            uploaded_by=user.id,
            revision=revision,
            markdown=f"# {name}",
            summary={"title": name},
        )

    files = [
        _file("main_v1.pdf", FileRole.MAIN, 1),
        _file("main_v2.pdf", FileRole.MAIN, 2),
        _file("support.pdf", FileRole.SUPPORT, None),
    ]

    # Commit in dependency order (users → projects → files) to satisfy FKs.
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()
    async with get_async_db_session() as session:
        for f in files:
            session.add(f)
        await session.commit()

    yield project

    async with get_async_db_session() as session:
        for f in files:
            obj = (
                await session.execute(select(File).where(col(File.id) == f.id))
            ).scalar_one_or_none()
            if obj:
                await session.delete(obj)
        proj = (
            await session.execute(select(Project).where(col(Project.id) == project.id))
        ).scalar_one_or_none()
        if proj:
            await session.delete(proj)
        usr = (
            await session.execute(select(User).where(col(User.id) == user.id))
        ).scalar_one_or_none()
        if usr:
            await session.delete(usr)
        await session.commit()


@pytest.mark.asyncio
async def test_returns_every_main_revision_and_supports(project_with_revisions):
    """All files are returned: every main-document revision plus shared support files."""
    items = await get_project_files_list_items(project_with_revisions.id)
    names = {i.file_name for i in items}
    assert names == {"main_v1.pdf", "main_v2.pdf", "support.pdf"}

    # The current main is the one matching the project's latest revision; the
    # other MAIN file is a previous revision.
    mains = {i.file_name: i.revision for i in items if i.role == FileRole.MAIN}
    assert mains == {"main_v1.pdf": 1, "main_v2.pdf": 2}


@pytest.mark.asyncio
async def test_never_reads_the_heavy_columns(project_with_revisions: Project) -> None:
    """The overview polls this list: markdown and summary must stay in the database."""
    statements: list[str] = []

    def _record(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        statements.append(statement)

    event.listen(async_engine.sync_engine, "before_cursor_execute", _record)
    try:
        items = await get_project_files_list_items(project_with_revisions.id)
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", _record)

    assert len(items) == 3
    selects = [s for s in statements if "FROM files" in s]
    assert selects
    assert not [s for s in selects if "files.markdown" in s or "files.summary" in s]
