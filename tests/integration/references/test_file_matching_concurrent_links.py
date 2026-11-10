"""A reference file matching run must keep the links made by hand.

A user can link a file to a reference while a matching run waits for its
dependencies or runs its LLM stage. The run persists its whole state after
every step, so it must carry the earlier run's matches into its own state and
must not save its stale snapshot over a link made in the meantime.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.references.service import MatchSource, add_file_to_reference
from lib.workflows.document_summarization.state import FileSummary
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatch,
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)
from lib.workflows.runner import run_workflow_from_config

TWO_STAGE_MATCH_PATH = (
    "lib.workflows.reference_file_matching.nodes.match_supporting_docs._two_stage_match"
)


class Seeded:
    """Ids of the rows one test project holds."""

    def __init__(self, project_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self.project_id = str(project_id)
        self.run_id = run_id
        self.auto_file = ""
        self.manual_file = ""


def _file(project_id: uuid.UUID, role: FileRole, name: str) -> File:
    return File(
        id=uuid.uuid4(),
        project_id=project_id,
        file_name=name,
        file_path=f"path/{name}",
        file_type="application/pdf",
        file_size=1,
        content_hash=str(uuid.uuid4()),
        role=role,
        revision=1 if role == FileRole.MAIN else None,
        markdown=f"# {name}",
        summary=None
        if role == FileRole.MAIN
        else {
            "title": name,
            "authors": "A",
            "publication_date": "2020",
            "abstract": "abstract",
            "summary": "summary",
        },
    )


def _run(
    project_id: uuid.UUID,
    type: WorkflowRunType,
    status: WorkflowRunStatus,
    state_json: dict | None,
) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        langgraph_thread_id=str(uuid.uuid4()),
        project_id=project_id,
        type=type,
        status=status,
        revision=1,
        state_json=state_json,
    )


async def _add(*rows: object) -> None:
    async with get_async_db_session() as session:
        for row in rows:
            session.add(row)
        await session.commit()


@pytest_asyncio.fixture
async def seeded() -> AsyncIterator[Seeded]:
    """A project with three references, one linked by hand in a finished
    matching run, and a new matching run that has not started yet."""
    project = Project(id=uuid.uuid4(), title="Concurrent manual links")
    main = _file(project.id, FileRole.MAIN, "main.pdf")
    auto_file = _file(project.id, FileRole.SUPPORT, "auto.pdf")
    manual_file = _file(project.id, FileRole.SUPPORT, "manual.pdf")
    extraction = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id=str(project.id)),
        file_id=str(main.id),
        extracted_references=[
            ExtractedReference(id=f"ref-{n}", text=f"Reference {n}") for n in (1, 2, 3)
        ],
    )
    earlier = ReferenceFileMatchingState(
        config=ReferenceFileMatchingConfig(project_id=str(project.id)),
        file_id=str(main.id),
        matches=[
            ReferenceFileMatch(
                reference_id="ref-1",
                file_id=str(manual_file.id),
                source=MatchSource.MANUAL_UPLOAD,
            )
        ],
    )
    pending = _run(
        project.id,
        WorkflowRunType.REFERENCE_FILE_MATCHING,
        WorkflowRunStatus.PENDING,
        None,
    )
    await _add(project)
    await _add(main, auto_file, manual_file)
    await _add(
        _run(
            project.id,
            WorkflowRunType.REFERENCE_EXTRACTION,
            WorkflowRunStatus.COMPLETED,
            extraction.model_dump(mode="json"),
        ),
        _run(
            project.id,
            WorkflowRunType.REFERENCE_FILE_MATCHING,
            WorkflowRunStatus.COMPLETED,
            earlier.model_dump(mode="json"),
        ),
    )
    await _add(pending)

    result = Seeded(project.id, pending.id)
    result.auto_file = str(auto_file.id)
    result.manual_file = str(manual_file.id)
    yield result

    async with get_async_db_session() as session:
        row = await session.get(Project, project.id)
        if row is not None:
            await session.delete(row)
            await session.commit()


def _auto_matcher(
    seeded: Seeded, during: Callable[[], Awaitable[object]] | None = None
) -> Callable[..., Awaitable[list[str | None]]]:
    """Stand-in for the LLM stage: matches every reference to the auto file,
    after running `during` (a link landing while the stage runs)."""

    async def fake(
        reference_texts: list[str], summaries: list[FileSummary], context: object
    ) -> list[str | None]:
        if during is not None:
            await during()
        return [seeded.auto_file for _ in reference_texts]

    return fake


async def _link_ref_2(seeded: Seeded) -> bool:
    return await add_file_to_reference(
        project_id=seeded.project_id,
        file_id=seeded.manual_file,
        reference_id="ref-2",
        source=MatchSource.MANUAL_UPLOAD,
        revision=1,
    )


async def _run_matching(seeded: Seeded, fake: Callable[..., object]) -> None:
    config = ReferenceFileMatchingConfig(
        project_id=seeded.project_id, openai_api_key="test-key"
    )
    user = User(id=uuid.uuid4(), email="matching@example.com", name="Matching")
    with patch(TWO_STAGE_MATCH_PATH, side_effect=fake):
        await run_workflow_from_config(
            config=config,
            thread_id=str(uuid.uuid4()),
            workflow_run_id=str(seeded.run_id),
            user=user,
            revision=1,
        )


async def _stored_matches(run_id: uuid.UUID) -> dict[str, tuple[str, str]]:
    async with get_async_db_session() as session:
        stored = (
            await session.execute(
                select(col(WorkflowRun.state_json)).where(col(WorkflowRun.id) == run_id)
            )
        ).scalar_one()
    state = ReferenceFileMatchingState.model_validate(stored)
    return {m.reference_id: (m.file_id, m.source.value) for m in state.matches}


def _expected(seeded: Seeded) -> dict[str, tuple[str, str]]:
    manual = (seeded.manual_file, MatchSource.MANUAL_UPLOAD.value)
    return {
        "ref-1": manual,
        "ref-2": manual,
        "ref-3": (seeded.auto_file, MatchSource.AUTO_MATCHED.value),
    }


@pytest.mark.asyncio
async def test_link_made_while_the_run_matches_survives(seeded: Seeded) -> None:
    linked: list[bool] = []

    async def link() -> None:
        linked.append(await _link_ref_2(seeded))

    await _run_matching(seeded, _auto_matcher(seeded, during=link))

    assert linked == [True]
    assert await _stored_matches(seeded.run_id) == _expected(seeded)


@pytest.mark.asyncio
async def test_link_made_while_the_run_waits_survives(seeded: Seeded) -> None:
    assert await _link_ref_2(seeded) is True

    await _run_matching(seeded, _auto_matcher(seeded))

    assert await _stored_matches(seeded.run_id) == _expected(seeded)
