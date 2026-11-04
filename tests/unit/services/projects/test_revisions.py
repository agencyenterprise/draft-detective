"""Which revision a request means, and the list of a project's revisions."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.services.projects import revisions
from lib.services.projects.revisions import (
    RevisionListItem,
    list_project_revisions,
    resolve_revision,
)


def _project(current_revision: int) -> Project:
    return Project(id=uuid.uuid4(), title="p", current_revision=current_revision)


def _main_file(project: Project, revision: int | None, name: str) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=project.id,
        file_name=name,
        role=FileRole.MAIN,
        revision=revision,
        created_at=datetime(2026, 1, revision or 1, tzinfo=UTC),
    )


def test_resolve_revision_defaults_to_the_current_revision():
    assert resolve_revision(_project(3), None) == 3


def test_resolve_revision_keeps_the_one_asked_for():
    assert resolve_revision(_project(3), 1) == 1


@pytest.mark.asyncio
async def test_lists_every_revision_with_its_main_file():
    project = _project(3)
    first = _main_file(project, 1, "v1.pdf")
    third = _main_file(project, 3, "v3.pdf")
    stray = _main_file(project, None, "no-revision.pdf")
    files = AsyncMock(return_value=[third, stray, first])

    with patch.object(revisions, "get_files_by_project_id", new=files):
        items = await list_project_revisions(project)

    files.assert_awaited_once_with(project.id, roles=[FileRole.MAIN])
    assert items == [
        RevisionListItem(
            revision=1,
            main_file_name="v1.pdf",
            main_file_id=str(first.id),
            created_at=first.created_at,
        ),
        # Created, but its main document not uploaded yet.
        RevisionListItem(revision=2),
        RevisionListItem(
            revision=3,
            main_file_name="v3.pdf",
            main_file_id=str(third.id),
            created_at=third.created_at,
        ),
    ]
