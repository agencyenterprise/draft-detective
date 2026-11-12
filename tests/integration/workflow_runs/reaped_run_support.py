"""The downloader state the reaped-run tests start their runs from."""

from lib.models.workflow_run import WorkflowRunType
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
)


def initial_state(project_id: str) -> ReferenceDownloaderState:
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER, project_id=project_id
        ),
        fetched_references=[
            ReferenceFetchResult(reference_id=ref, input_reference=ref)
            for ref in ("r1", "r2")
        ],
    )
