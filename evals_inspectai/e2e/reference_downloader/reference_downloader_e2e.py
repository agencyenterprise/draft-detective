import json
from pathlib import Path
from typing import List, Optional

from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from evals_inspectai.common.backend import local_backend_for, resolve_base_url
from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    poll_workflow_run_until_complete,
    start_workflow,
)
from evals_inspectai.common.api_solver import surface_conversations
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.local_backend import LocalBackend
from evals_inspectai.common.scorers import structured_output_scorer


class ReferenceFetchItemOutput(BaseModel):
    """Local mirror of ReferenceFetchItem from the reference_downloader workflow."""

    final_conclusion: str = ""
    source_url: Optional[str] = None
    inaccessibility_reason: Optional[str] = None


class ReferenceFetchResultOutput(BaseModel):
    """Local mirror of ReferenceFetchResult from the reference_downloader workflow state."""

    reference_id: str = ""
    input_reference: str = ""
    status: str = ""
    result: Optional[ReferenceFetchItemOutput] = None
    error: Optional[str] = None


class ReferenceDownloaderOutput(BaseModel):
    """Local mirror of ReferenceDownloaderState for output parsing."""

    fetched_references: List[ReferenceFetchResultOutput] = Field(default_factory=list)


def _record_to_sample(record: dict) -> Sample:
    return Sample(
        input=record["input"],
        target=record.get("target_final_conclusion", ""),
    )


@task
def reference_downloader_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
):
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        _record_to_sample,
    )

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=_reference_downloader_api_agent(
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=structured_output_scorer(
            ReferenceDownloaderOutput, _compare_final_conclusion
        ),
    )


@agent
def _reference_downloader_api_agent(
    timeout_s: float = 600,
    poll_interval_s: float = 5,
    local_backend: LocalBackend | None = None,
    api_base_url: str | None = None,
) -> Agent:
    """Run the reference_downloader workflow via the API for a single reference."""

    async def execute(state: AgentState) -> AgentState:
        base_url = await resolve_base_url(local_backend, api_base_url)

        reference = state.messages[0].text if state.messages else ""

        project_id = await create_project_and_start_workflows(
            file_content=f"## References\n\n{reference}",
            file_name="eval-document.md",
            workflow_types=["document_processing", "reference_extraction"],
            base_url=base_url,
        )

        workflow_run_id = await start_workflow(
            {
                "type": "reference_downloader",
                "project_id": project_id,
                "references": [{"reference_id": "ref-1", "text": reference}],
            },
            base_url=base_url,
        )

        try:
            run_detail = await poll_workflow_run_until_complete(
                workflow_run_id,
                timeout_s=timeout_s,
                interval_s=poll_interval_s,
                base_url=base_url,
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}
        _check_item_errors(workflow_state)

        await surface_conversations(
            state,
            workflow_state,
            "reference_downloader",
            item_messages_key="fetched_references",
            item_label="reference",
        )

        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return execute


def _check_item_errors(workflow_state: dict) -> None:
    """Raise if any fetched reference has a per-item error."""
    for item in workflow_state.get("fetched_references", []):
        if isinstance(item, dict) and item.get("error"):
            raise WorkflowCompletionError(
                f"Reference '{item.get('input_reference', '?')}' "
                f"failed: {item['error']}"
            )


def _compare_final_conclusion(
    output: ReferenceDownloaderOutput, state: TaskState
) -> Score:
    """Deterministic: the reference's final download conclusion equals the target exactly."""
    if not output.fetched_references:
        return Score(value=INCORRECT, explanation="No fetched references found")

    first = output.fetched_references[0]
    if first.result is None:
        return Score(value=INCORRECT, explanation="No result found")

    actual = first.result.final_conclusion
    expected = state.target.text
    if actual == expected:
        return Score(value=CORRECT, explanation=f"final_conclusion matches: {actual}")
    return Score(
        value=INCORRECT,
        explanation=f"Expected '{expected}', got '{actual}'",
    )
