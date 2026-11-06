"""An in-memory stand-in for `get_files_by_project_id`, for unit tests.

It filters rows the way the SQL does, shared rows (revision IS NULL) included,
so a test can hold the rows a project has and let every lookup built on the
query see them.
"""

import importlib
import uuid
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from lib.models.file import File, FileRole


def fake_file_query(
    rows: list[File],
) -> Callable[..., Awaitable[list[File]]]:
    async def query(
        project_id: uuid.UUID | str,
        roles: Sequence[FileRole],
        revision: int | None = None,
        file_ids: Sequence[uuid.UUID] | None = None,
    ) -> list[File]:
        return [
            f
            for f in rows
            if str(f.project_id) == str(project_id)
            and f.role in roles
            and (revision is None or f.revision in (revision, None))
            and (file_ids is None or f.id in file_ids)
        ]

    return query


def file_row(
    project_id: uuid.UUID, role: FileRole, revision: int | None, name: str = ""
) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=project_id,
        file_name=name or f"{role.value}.docx",
        file_path="/tmp/x",
        file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=1,
        content_hash="h",
        role=role,
        uploaded_by=uuid.uuid4(),
        revision=revision,
    )


@contextmanager
def patched_file_query(rows: list[File], *modules: str) -> Iterator[None]:
    """Serve `rows` to the file query in the service and in each module given
    that imports it by name."""
    query = fake_file_query(rows)
    with ExitStack() as stack:
        for module in ("lib.services.files.service", *modules):
            if hasattr(importlib.import_module(module), "get_files_by_project_id"):
                stack.enter_context(patch(f"{module}.get_files_by_project_id", query))
        yield
