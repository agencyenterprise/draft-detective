"""Turn the reference fetches that failed into run-level errors."""

from lib.workflows.models import WorkflowError, WorkflowErrorSeverity
from lib.workflows.reference_downloader.fetch_logging import short_reference
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)


def fetch_errors(
    state: ReferenceDownloaderState, workflow_run_id: str | None
) -> list[WorkflowError]:
    """One error per reference this run failed to fetch.

    A failed fetch costs one reference, not the run, so it is a warning while
    other references in the run got an answer (a source found or not). When
    none did, the run must not read as a clean completion, so the failures
    escalate to errors.
    """
    fetched = _fetched_this_run(state)
    produced_results = any(
        item.status == ReferenceFetchStatus.COMPLETED for item in fetched
    )
    severity = (
        WorkflowErrorSeverity.WARNING
        if produced_results
        else WorkflowErrorSeverity.ERROR
    )
    return [
        WorkflowError(
            task_name="fetch_single_reference",
            error=_fetch_error_message(item),
            workflow_run_id=workflow_run_id,
            severity=severity,
            details=item.error_details,
        )
        for item in fetched
        if item.status == ReferenceFetchStatus.ERROR
    ]


def _fetched_this_run(state: ReferenceDownloaderState) -> list[ReferenceFetchResult]:
    """The results of the references this run fetched.

    `fetched_references` carries earlier runs' results forward. Those must
    neither be reported again nor count as this run's output, or a run where
    every fetch failed would read as a partial success.
    """
    requested = set(state.run_reference_ids)
    return [item for item in state.fetched_references if item.reference_id in requested]


def _fetch_error_message(item: ReferenceFetchResult) -> str:
    """State what the reader lost; the exception itself stays on `details`."""
    return (
        f'Reference "{short_reference(item.input_reference)}" could not be '
        f"fetched, so it has no downloaded source. {item.error or 'Unknown error'}"
    )
