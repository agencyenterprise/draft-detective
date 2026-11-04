"""A project's revisions: which one a request means, and the list of them all.

Revisions run from 1 to ``Project.current_revision``. Each has at most one
MAIN file, the main document uploaded for it; a revision created but not yet
uploaded to has none.
"""

from datetime import datetime

from pydantic import BaseModel

from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.services.files.service import get_files_by_project_id


class RevisionListItem(BaseModel):
    """Summary of a single project revision."""

    revision: int
    main_file_name: str | None = None
    main_file_id: str | None = None
    created_at: datetime | None = None


def resolve_revision(project: Project, revision: int | None) -> int:
    """The revision a request asked for, or the project's current one when it
    named none."""
    return revision if revision is not None else project.current_revision


async def list_project_revisions(project: Project) -> list[RevisionListItem]:
    """Every revision of the project, oldest first, with its main file if any."""
    main_files = await get_files_by_project_id(project.id, roles=[FileRole.MAIN])
    main_by_revision: dict[int, File] = {
        f.revision: f for f in main_files if f.revision is not None
    }
    return [
        _revision_item(rev, main_by_revision.get(rev))
        for rev in range(1, project.current_revision + 1)
    ]


def _revision_item(revision: int, main_file: File | None) -> RevisionListItem:
    if main_file is None:
        return RevisionListItem(revision=revision)
    return RevisionListItem(
        revision=revision,
        main_file_name=main_file.file_name,
        main_file_id=str(main_file.id),
        created_at=main_file.created_at,
    )
