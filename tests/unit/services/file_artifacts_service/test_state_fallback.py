"""FileArtifactsService reading workflow state when the DB has no cached copy.

Each getter looks up the run of one workflow type for the project and revision,
and answers from that run's state, or raises when the run or its state is
missing. References read the file matching state too, but only when it exists.
"""

from contextlib import AbstractContextManager
from unittest.mock import AsyncMock, patch

import pytest

from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.files.document import FileDocument
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.workflow_types import WorkflowState

MODULE = "lib.services.file_artifacts_service.file_artifacts_service"
PROJECT_ID = "project-1"


def _extraction_state() -> ReferenceExtractionState:
    return ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id=PROJECT_ID),
        file_id="main",
        extracted_references=[ExtractedReference(id="ref-1", text="Smith 2020")],
    )


def _patch_runs(
    states: dict[WorkflowRunType, WorkflowState | None],
) -> tuple[AbstractContextManager[object], AbstractContextManager[object]]:
    """Serve one run per type in ``states``, holding that state (or none).

    The run type itself stands in for the run row.
    """

    async def run_by_type(
        project_id: str,
        run_type: WorkflowRunType,
        revision: int,
        include_state: bool,
    ) -> WorkflowRunType | None:
        assert (project_id, revision, include_state) == (PROJECT_ID, 2, True)
        return run_type if run_type in states else None

    async def read_state(run: WorkflowRunType) -> WorkflowState | None:
        return states[run]

    return (
        patch(f"{MODULE}.get_project_workflow_run_by_type", side_effect=run_by_type),
        patch(f"{MODULE}.read_workflow_run_state", side_effect=read_state),
    )


async def _extracted_references(
    states: dict[WorkflowRunType, WorkflowState | None],
) -> list[ExtractedReference]:
    run_patch, state_patch = _patch_runs(states)
    with run_patch, state_patch:
        return await FileArtifactsService(PROJECT_ID, 2).get_extracted_references()


@pytest.mark.asyncio
async def test_extracted_references_come_from_the_extraction_state() -> None:
    state = _extraction_state()

    references = await _extracted_references(
        {WorkflowRunType.REFERENCE_EXTRACTION: state}
    )

    assert references == state.extracted_references


@pytest.mark.asyncio
async def test_extracted_references_raise_without_an_extraction_run() -> None:
    with pytest.raises(ValueError, match="No workflow run found"):
        await _extracted_references({})


@pytest.mark.asyncio
async def test_extracted_references_raise_when_the_run_has_no_state() -> None:
    with pytest.raises(ValueError, match="No state found"):
        await _extracted_references({WorkflowRunType.REFERENCE_EXTRACTION: None})


@pytest.mark.asyncio
async def test_references_without_a_matching_run_have_no_supporting_file() -> None:
    run_patch, state_patch = _patch_runs(
        {WorkflowRunType.REFERENCE_EXTRACTION: _extraction_state()}
    )
    service = FileArtifactsService(PROJECT_ID, 2)

    with run_patch, state_patch, patch.object(service, "get_project_files") as files:
        references = await service.get_references()

    files.assert_not_called()
    assert [(r.reference_id, r.file_id) for r in references] == [("ref-1", None)]


@pytest.mark.asyncio
async def test_main_file_falls_back_to_the_processing_state() -> None:
    main = FileDocument(
        file_name="main.docx",
        file_path="main.docx",
        file_type="application/docx",
        markdown="# Main",
        markdown_token_count=2,
        file_id="main",
    )
    state = DocumentProcessingState(
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        config=DocumentProcessingWorkflowConfig(
            type=WorkflowRunType.DOCUMENT_PROCESSING, project_id=PROJECT_ID
        ),
        file=main,
    )
    run_patch, state_patch = _patch_runs({WorkflowRunType.DOCUMENT_PROCESSING: state})
    service = FileArtifactsService(PROJECT_ID, 2)

    with (
        run_patch,
        state_patch,
        patch.object(service, "_load_main_files", AsyncMock(return_value=[])),
    ):
        assert await service.get_main_file() == main
