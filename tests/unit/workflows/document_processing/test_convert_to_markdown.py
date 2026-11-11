"""A main document that yields no text must end document processing FAILED.

Document processing is the required dependency of every assessment, and a
FAILED run cascade-cancels them. A run that completes "with errors" instead
lets reference extraction and the rest spend model calls on an empty document.
These tests drive the real graph through `run_workflow`, with only conversion
and the database stubbed.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from lib.models.workflow_run import WorkflowRunFailureReason, WorkflowRunStatus
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.services.files.document import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.graph import build_document_processing_graph
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.runner import run_workflow

NODE = "lib.workflows.document_processing.nodes.convert_to_markdown"
PROJECT_ID = str(uuid4())


def _document(name: str, markdown: str = "") -> FileDocument:
    return FileDocument(
        file_id=str(uuid4()),
        file_name=name,
        file_path=f"/uploads/{name}",
        file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        markdown=markdown,
        markdown_token_count=0,
    )


class _Run:
    def __init__(self) -> None:
        self.fail = AsyncMock()
        self.update_status = AsyncMock()

    @property
    def completed(self) -> bool:
        return any(
            c.args[1] == WorkflowRunStatus.COMPLETED
            for c in self.update_status.await_args_list
        )


@pytest.fixture
def run() -> Iterator[_Run]:
    """Stub every database call the runner and the node decorator make."""
    stubs = _Run()
    with (
        patch("lib.workflows.runner.update_workflow_run_status", stubs.update_status),
        patch("lib.workflows.runner.fail_workflow_run", stubs.fail),
        patch("lib.workflows.runner.persist_workflow_run_state", AsyncMock()),
        patch("lib.workflows.runner._persist_issues_from_state", AsyncMock()),
        patch("lib.workflows.decorators.get_or_create_progress", return_value=uuid4()),
        patch("lib.workflows.decorators.increment_and_complete_if_done", AsyncMock()),
        patch(
            "lib.services.workflow_runs.service.get_workflow_run_status",
            return_value=WorkflowRunStatus.RUNNING,
        ),
        patch(
            "lib.services.workflow_runs.service.update_workflow_run_heartbeat",
            AsyncMock(),
        ),
        patch(f"{NODE}.update_file_artifacts", AsyncMock()),
    ):
        yield stubs


async def _process(main: FileDocument, convert: AsyncMock) -> None:
    run_id = str(uuid4())
    state = DocumentProcessingState(
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        file=main,
        supporting_files=[],
        config=DocumentProcessingWorkflowConfig(
            type=WorkflowRunType.DOCUMENT_PROCESSING, project_id=PROJECT_ID
        ),
    )
    context = ContextSchema(
        project_id=PROJECT_ID,
        workflow_run_id=run_id,
        file_artifacts_service=MockFileArtifactsService(),
    )
    with patch(f"{NODE}.convert_file_document_to_markdown", convert):
        await run_workflow(
            workflow_run_id=run_id,
            workflow_type=WorkflowRunType.DOCUMENT_PROCESSING,
            graph=build_document_processing_graph(),
            state=state,
            context=context,
            thread_id=str(uuid4()),
        )


def _failure_message(run: _Run) -> str:
    run.fail.assert_awaited_once()
    kwargs = run.fail.await_args_list[0].kwargs
    assert kwargs["failure_reason"] == WorkflowRunFailureReason.UNHANDLED_EXCEPTION
    return kwargs["failure_message"]


@pytest.mark.asyncio
async def test_main_conversion_error_fails_the_run(run: _Run) -> None:
    convert = AsyncMock(side_effect=ValueError("File is not a zip file"))

    await _process(_document("broken.docx"), convert)

    assert not run.completed
    message = _failure_message(run)
    assert "broken.docx" in message
    assert "File is not a zip file" in message


@pytest.mark.asyncio
async def test_main_document_without_text_fails_the_run(run: _Run) -> None:
    blank = _document("blank.docx")
    convert = AsyncMock(return_value=blank.model_copy(update={"markdown": " \n\n"}))

    await _process(blank, convert)

    assert not run.completed
    assert "blank.docx" in _failure_message(run)


@pytest.mark.asyncio
async def test_main_document_with_text_completes(run: _Run) -> None:
    main = _document("paper.docx")
    convert = AsyncMock(return_value=main.model_copy(update={"markdown": "# Title"}))

    await _process(main, convert)

    assert run.completed
    run.fail.assert_not_awaited()
