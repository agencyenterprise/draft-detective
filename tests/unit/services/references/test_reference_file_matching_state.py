"""Unit tests for how lib.services.references.service loads (and seeds) the
ReferenceFileMatching state, exercised through get_file_reference_matches."""

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.references.service import get_file_reference_matches
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)

PROJECT_ID = str(uuid.uuid4())
MAIN_FILE_ID = str(uuid.uuid4())
SUPPORTING_IDS = [str(uuid.uuid4()), str(uuid.uuid4())]


def _make_run(state_json: dict | None) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.state_json = state_json
    return run


@pytest.fixture
def svc() -> Iterator[SimpleNamespace]:
    """Patch every collaborator of the state loader; tests set return values."""
    target = "lib.services.references.service"
    runs = "lib.services.workflow_runs.service"
    get_run = AsyncMock()
    with (
        # The loader reads the run through the shared run service; the seeding
        # path looks it up again from the references service.
        patch(f"{target}.get_project_workflow_run_by_type", new=get_run),
        patch(f"{runs}.get_project_workflow_run_by_type", new=get_run),
        patch(f"{runs}.read_workflow_run_state", new=AsyncMock()) as read_state,
        patch(
            f"{target}.get_main_file_id", new=AsyncMock(return_value=MAIN_FILE_ID)
        ) as main_file,
        patch(
            f"{target}.get_processed_supporting_file_ids",
            new=AsyncMock(return_value=SUPPORTING_IDS),
        ),
        patch(f"{target}.create_workflow_run", new=AsyncMock()) as create_run,
        patch(f"{target}.persist_workflow_run_state", new=AsyncMock()) as persist,
    ):
        yield SimpleNamespace(
            get_run=get_run,
            read_state=read_state,
            main_file=main_file,
            create_run=create_run,
            persist=persist,
        )


@pytest.mark.asyncio
async def test_returns_matches_from_existing_state_without_writing(svc):
    match = ReferenceFileMatch(
        reference_id="r1", file_id="f1", source=MatchSource.AUTO_MATCHED
    )
    svc.get_run.return_value = _make_run(state_json={"stored": True})
    svc.read_state.return_value = ReferenceFileMatchingState(
        type=WorkflowRunType.REFERENCE_FILE_MATCHING,
        config=ReferenceFileMatchingConfig(project_id=PROJECT_ID),
        file_id=MAIN_FILE_ID,
        matches=[match],
    )

    assert await get_file_reference_matches(PROJECT_ID, revision=1) == [match]
    svc.main_file.assert_not_awaited()
    svc.create_run.assert_not_awaited()
    svc.persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_main_file_returns_empty_without_creating_a_run(svc):
    svc.get_run.return_value = None
    svc.main_file.side_effect = ValueError("no main file")

    assert await get_file_reference_matches(PROJECT_ID, revision=1) == []
    svc.create_run.assert_not_awaited()
    svc.persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_run_is_created_and_seeded_with_default_state(svc):
    created = _make_run(state_json=None)
    svc.get_run.side_effect = [None, created]

    assert await get_file_reference_matches(PROJECT_ID, revision=3) == []

    create_kwargs = svc.create_run.await_args.kwargs
    assert create_kwargs["project_id"] == PROJECT_ID
    assert create_kwargs["type"] == WorkflowRunType.REFERENCE_FILE_MATCHING
    assert create_kwargs["revision"] == 3
    run_id, seeded = svc.persist.await_args.args
    assert run_id == str(created.id)
    assert seeded.file_id == MAIN_FILE_ID
    assert seeded.supporting_file_ids == SUPPORTING_IDS
    assert seeded.config.project_id == PROJECT_ID
    assert seeded.matches == []


@pytest.mark.asyncio
async def test_existing_run_without_persisted_state_is_seeded(svc):
    run = _make_run(state_json=None)
    svc.get_run.return_value = run
    svc.read_state.return_value = None

    assert await get_file_reference_matches(PROJECT_ID, revision=1) == []

    svc.create_run.assert_not_awaited()
    run_id, seeded = svc.persist.await_args.args
    assert run_id == str(run.id)
    assert seeded.matches == []


@pytest.mark.asyncio
async def test_existing_state_that_fails_to_hydrate_is_not_overwritten(svc):
    """state_json is present but read_workflow_run_state can't parse it (schema
    drift): callers get an empty default, and the stored payload stays intact."""
    svc.get_run.return_value = _make_run(state_json={"matches": "legacy shape"})
    svc.read_state.return_value = None

    assert await get_file_reference_matches(PROJECT_ID, revision=1) == []

    svc.create_run.assert_not_awaited()
    svc.persist.assert_not_awaited()
