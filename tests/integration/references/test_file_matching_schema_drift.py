"""Linking a file to a reference must not overwrite a ReferenceFileMatching
state that no longer validates.

A schema change to the state can leave a stored state_json that fails to
hydrate. Treating it like a missing state would append the new link to an
empty default and persist that over the row, dropping every earlier match.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.references.service import MatchSource, add_file_to_reference
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)

# A stored matching state written by an older schema: the matches are real,
# but the top-level shape no longer validates (file_id is missing).
DRIFTED_STATE = {
    "type": WorkflowRunType.REFERENCE_FILE_MATCHING.value,
    "matches": [
        {"reference_id": "ref-1", "file_id": "earlier-file", "source": "auto_matched"}
    ],
}


async def _add(*rows: object) -> None:
    async with get_async_db_session() as session:
        for row in rows:
            session.add(row)
        await session.commit()


def _run(project_id: uuid.UUID, type: WorkflowRunType, state_json: dict) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        langgraph_thread_id=str(uuid.uuid4()),
        project_id=project_id,
        type=type,
        status=WorkflowRunStatus.COMPLETED,
        revision=1,
        state_json=state_json,
    )


@pytest_asyncio.fixture
async def drifted_project() -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """A project whose matching run holds a drifted state with one match."""
    project = Project(id=uuid.uuid4(), title="Drifted matching state")
    main = File(
        id=uuid.uuid4(),
        project_id=project.id,
        file_name="main.pdf",
        file_path="path/main.pdf",
        file_type="application/pdf",
        file_size=1,
        content_hash=str(uuid.uuid4()),
        role=FileRole.MAIN,
        revision=1,
        markdown="# main",
    )
    extraction = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id=str(project.id)),
        file_id=str(main.id),
        extracted_references=[
            ExtractedReference(id="ref-1", text="One"),
            ExtractedReference(id="ref-2", text="Two"),
        ],
    )
    matching = _run(project.id, WorkflowRunType.REFERENCE_FILE_MATCHING, DRIFTED_STATE)
    await _add(project)
    await _add(main)
    await _add(
        _run(
            project.id,
            WorkflowRunType.REFERENCE_EXTRACTION,
            extraction.model_dump(mode="json"),
        ),
        matching,
    )

    yield project.id, matching.id

    async with get_async_db_session() as session:
        for model, row_id in ((File, main.id), (Project, project.id)):
            row = (
                await session.execute(select(model).where(col(model.id) == row_id))
            ).scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()


@pytest.mark.asyncio
async def test_link_does_not_overwrite_a_state_that_fails_to_validate(
    drifted_project: tuple[uuid.UUID, uuid.UUID],
) -> None:
    project_id, matching_run_id = drifted_project

    linked = await add_file_to_reference(
        project_id=str(project_id),
        file_id="new-file",
        reference_id="ref-2",
        source=MatchSource.MANUAL_UPLOAD,
        revision=1,
    )

    assert linked is False
    async with get_async_db_session() as session:
        stored = (
            await session.execute(
                select(col(WorkflowRun.state_json)).where(
                    col(WorkflowRun.id) == matching_run_id
                )
            )
        ).scalar_one()
    assert stored == DRIFTED_STATE
