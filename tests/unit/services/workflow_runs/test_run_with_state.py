"""get_project_workflow_run_with_state: a project's run of one type, with its state
as the class that names the type."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.workflow_runs.service import get_project_workflow_run_with_state
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)

MODULE = "lib.services.workflow_runs.service"


def _patch(run: MagicMock | None, state: object):
    return (
        patch(
            f"{MODULE}.get_project_workflow_run_by_type",
            new=AsyncMock(return_value=run),
        ),
        patch(f"{MODULE}.read_workflow_run_state", new=AsyncMock(return_value=state)),
    )


def _extraction_state() -> ReferenceExtractionState:
    return ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id="p-1"), file_id="main"
    )


@pytest.mark.asyncio
async def test_looks_up_the_type_the_state_class_pins_with_its_state():
    run = MagicMock()
    state = _extraction_state()
    get_run, read_state = _patch(run, state)
    with get_run as lookup, read_state as read:
        result = await get_project_workflow_run_with_state(
            "p-1", ReferenceExtractionState, revision=3
        )

    assert result == (run, state)
    lookup.assert_awaited_once_with(
        "p-1", WorkflowRunType.REFERENCE_EXTRACTION, revision=3, include_state=True
    )
    read.assert_awaited_once_with(run)


@pytest.mark.asyncio
async def test_no_run_has_no_state():
    get_run, read_state = _patch(None, None)
    with get_run, read_state as read:
        result = await get_project_workflow_run_with_state(
            "p-1", ReferenceExtractionState, revision=1
        )

    assert result == (None, None)
    read.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_run_without_state_is_returned_alone():
    run = MagicMock()
    get_run, read_state = _patch(run, None)
    with get_run, read_state:
        result = await get_project_workflow_run_with_state(
            "p-1", ReferenceExtractionState, revision=1
        )

    assert result == (run, None)


@pytest.mark.asyncio
async def test_a_state_of_another_class_is_refused():
    wrong = MagicMock(spec=DocumentProcessingState)
    get_run, read_state = _patch(MagicMock(), wrong)
    with get_run, read_state, pytest.raises(TypeError):
        await get_project_workflow_run_with_state(
            "p-1", ReferenceExtractionState, revision=1
        )
