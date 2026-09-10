"""WorkflowRunDetail carries the run row and the hydrated state. Serializing
the row's raw ``state_json`` too doubled every project payload with an exact
copy of ``state``; the response must emit the state once."""

from datetime import datetime, timezone
from uuid import uuid4

from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunPublic,
    WorkflowRunStatus,
    WorkflowRunType,
)
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
    return WorkflowRunDetail(
        run=WorkflowRunPublic.model_validate(run),
        state=state,
        state_status=WorkflowStateStatus.OK,
    )


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


def test_run_keeps_a_typed_schema_in_the_api_contract():
    """The generated frontend client relies on the run's declared fields and
    date types; excluding state_json must not degrade `run` to a bare object."""
    schema = WorkflowRunDetail.model_json_schema()
    run_ref = schema["properties"]["run"]
    assert run_ref == {"$ref": "#/$defs/WorkflowRunPublic"}
    run_schema = schema["$defs"]["WorkflowRunPublic"]
    assert "state_json" not in run_schema["properties"]
    for field in ("id", "type", "status", "created_at", "started_at", "completed_at"):
        assert field in run_schema["properties"]
    assert run_schema["properties"]["created_at"]["format"] == "date-time"


def test_run_is_built_from_the_orm_row_by_attribute():
    detail = _detail()

    assert isinstance(detail.run, WorkflowRunPublic)
    assert detail.run.type == WorkflowRunType.DOCUMENT_SUMMARIZATION
    assert detail.run.status == WorkflowRunStatus.COMPLETED
