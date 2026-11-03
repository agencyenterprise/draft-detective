"""Tests for how the reference downloader reports references it failed to fetch.

A failed fetch costs one reference, not the run, so it is reported as a warning
while other references got an answer. When none did, the run must not read as
a clean completion, so the failures escalate to errors. References carried
forward from an earlier run but not fetched in this one neither are reported
again nor count as this run's output.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lib.workflows.models import ErrorDetails, WorkflowErrorSeverity, WorkflowRunType
from lib.workflows.reference_downloader.nodes import fetch_references
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderInputItem,
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)

RUN_ID = "9a3b2c1d-7e6f-4a5b-8c9d-0e1f2a3b4c5d"
REFERENCE = "Smith, J. (2020). A study of things. Journal of Studies, 12(3), 45-67."


def _item(
    reference_id: str, status: ReferenceFetchStatus, error: str | None = None
) -> ReferenceFetchResult:
    return ReferenceFetchResult(
        reference_id=reference_id,
        input_reference=REFERENCE,
        status=status,
        error=error,
        error_details=ErrorDetails(error_type="TimeoutError") if error else None,
    )


def _state(
    *items: ReferenceFetchResult, run: list[str] | None = None
) -> ReferenceDownloaderState:
    """A state whose run fetched `run`, or every item when not given."""
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER, project_id="project-1"
        ),
        fetched_references=list(items),
        run_reference_ids=(
            run if run is not None else [item.reference_id for item in items]
        ),
    )


async def _cleanup(state: ReferenceDownloaderState) -> dict:
    # Call the node body directly: the register_node wrapper only adds progress
    # tracking, which needs a database. The file housekeeping is patched out.
    runtime = SimpleNamespace(
        context=SimpleNamespace(project_id="project-1", workflow_run_id=RUN_ID)
    )
    with (
        patch.object(
            fetch_references,
            "get_supporting_candidate_files",
            AsyncMock(return_value=[]),
        ),
        patch.object(fetch_references, "log_run_summary"),
    ):
        return await fetch_references.cleanup_failed_resources.__wrapped__(
            state, runtime
        )


@pytest.mark.asyncio
async def test_failed_fetch_keeps_its_error_details():
    agent = SimpleNamespace(ainvoke=AsyncMock(side_effect=TimeoutError("timed out")))
    runtime = SimpleNamespace(context=SimpleNamespace(project_id="project-1"))
    with patch.object(fetch_references, "ReferenceFetcherAgent", return_value=agent):
        result = await fetch_references.fetch_single_reference.__wrapped__(
            {"reference": REFERENCE, "reference_id": "ref-1"}, runtime
        )

    item = result["fetched_references"][0]
    assert item.status == ReferenceFetchStatus.ERROR
    assert item.error == "timed out"
    assert item.error_details is not None
    assert item.error_details.error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_every_fetch_failing_is_a_blocking_error():
    result = await _cleanup(
        _state(
            _item("ref-1", ReferenceFetchStatus.ERROR, "timed out"),
            _item("ref-2", ReferenceFetchStatus.ERROR, "timed out"),
        )
    )

    errors = result["errors"]
    assert [e.severity for e in errors] == [
        WorkflowErrorSeverity.ERROR,
        WorkflowErrorSeverity.ERROR,
    ]
    assert errors[0].task_name == "fetch_single_reference"
    assert errors[0].workflow_run_id == RUN_ID
    assert errors[0].details is not None
    assert errors[0].details.error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_failed_fetch_is_a_warning_while_others_completed():
    result = await _cleanup(
        _state(
            _item("ref-1", ReferenceFetchStatus.COMPLETED),
            _item("ref-2", ReferenceFetchStatus.ERROR, "timed out"),
        )
    )

    assert [e.severity for e in result["errors"]] == [WorkflowErrorSeverity.WARNING]


@pytest.mark.asyncio
async def test_failed_fetch_message_names_the_reference_and_the_cause():
    result = await _cleanup(
        _state(_item("ref-2", ReferenceFetchStatus.ERROR, "timed out"))
    )

    message = result["errors"][0].error
    assert "Smith, J. (2020)" in message
    assert "timed out" in message


@pytest.mark.asyncio
async def test_failures_carried_from_an_earlier_run_are_not_reported_again():
    """Fetching one reference must not re-raise another reference's old failure."""
    result = await _cleanup(
        _state(
            _item("ref-1", ReferenceFetchStatus.COMPLETED),
            _item("ref-2", ReferenceFetchStatus.ERROR, "old failure"),
            run=["ref-1"],
        )
    )

    assert result["errors"] == []


@pytest.mark.asyncio
async def test_completions_carried_from_an_earlier_run_do_not_downgrade_failures():
    """A run where every fetch failed is a failed run, whatever came before."""
    result = await _cleanup(
        _state(
            _item("ref-1", ReferenceFetchStatus.COMPLETED),
            _item("ref-2", ReferenceFetchStatus.ERROR, "timed out"),
            run=["ref-2"],
        )
    )

    assert [e.severity for e in result["errors"]] == [WorkflowErrorSeverity.ERROR]


@pytest.mark.asyncio
async def test_initialize_records_the_references_this_run_fetches():
    state = ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER,
            project_id="project-1",
            references=[
                ReferenceDownloaderInputItem(reference_id="ref-2", text=REFERENCE)
            ],
        ),
        fetched_references=[_item("ref-1", ReferenceFetchStatus.ERROR, "old")],
    )
    runtime = SimpleNamespace(context=SimpleNamespace(project_id="project-1"))

    result = await fetch_references.initialize_references.__wrapped__(state, runtime)

    assert result["run_reference_ids"] == ["ref-2"]


@pytest.mark.asyncio
async def test_completed_and_cancelled_fetches_report_no_errors():
    result = await _cleanup(
        _state(
            _item("ref-1", ReferenceFetchStatus.COMPLETED),
            _item("ref-2", ReferenceFetchStatus.CANCELLED),
        )
    )

    assert result["errors"] == []
