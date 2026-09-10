"""WorkflowRunDetail carries the run row and the hydrated state. Serializing
the row's raw ``state_json`` too doubled every project payload with an exact
copy of ``state``; the response must emit the state once."""

from datetime import datetime, timezone
from uuid import uuid4

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs import WorkflowRunDetail, WorkflowStateStatus
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    DocumentSummarizationWorkflowConfig,
)


def _detail() -> WorkflowRunDetail:
    project_id = uuid4()
    state = DocumentSummarizationState(
        type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
        config=DocumentSummarizationWorkflowConfig(
            type=WorkflowRunType.DOCUMENT_SUMMARIZATION, project_id=str(project_id)
        ),
        main_file_id="main",
        supporting_file_ids=["s1"],
        summaries=[],
    )
    run = WorkflowRun(
        id=uuid4(),
        project_id=project_id,
        type=WorkflowRunType.DOCUMENT_SUMMARIZATION,
        status=WorkflowRunStatus.COMPLETED,
        langgraph_thread_id="thread",
        revision=1,
        created_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
        state_json=state.model_dump(mode="json"),
    )
    return WorkflowRunDetail(run=run, state=state, state_status=WorkflowStateStatus.OK)


def test_run_is_serialized_without_raw_state_json():
    data = _detail().model_dump(mode="json")

    assert "state_json" not in data["run"]
    # Everything else about the run is still there.
    assert data["run"]["type"] == "document_summarization"
    assert data["run"]["status"] == "completed"
    assert data["run"]["revision"] == 1
    assert "langgraph_thread_id" in data["run"]


def test_hydrated_state_is_still_serialized_once():
    data = _detail().model_dump(mode="json")

    assert data["state"]["main_file_id"] == "main"
    assert data["state"]["supporting_file_ids"] == ["s1"]
    assert data["state_status"] == "ok"


def test_python_mode_dump_also_drops_state_json():
    data = _detail().model_dump()

    assert "state_json" not in data["run"]
    assert data["state"] is not None
