"""Start and list review-assistant runs that are handed their inputs.

The output-first review assistant page lets the user pick the output they want
and then any project file for each of its inputs. This module turns that pick
into the run's ``input_files`` (slot -> file IDs), rejecting anything the
workflow cannot run on, and reads those runs back with the inputs they used.
"""

import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import File, FileRole
from lib.models.workflow_run import WorkflowRunPublic
from lib.services.workflow_runs import (
    get_project_workflow_runs_by_type,
    get_workflow_run,
    hydrate_workflow_run_state,
    persist_workflow_run_state,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.review_assistant.inputs import (
    REVIEW_OUTPUT_SPECS,
    ReviewInputSlot,
)
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
)

# Any uploaded document can fill any slot: a reviewer memo that was uploaded
# as a supporting document is still the reviewer's memo. Derived files
# (extracted images, download candidates) are not documents.
_PICKABLE_ROLES = [
    FileRole.MAIN,
    FileRole.SUPPORT,
    FileRole.REVIEWER_MEMO,
    FileRole.RESPONSE_MEMO,
]


class ReviewInputsError(ValueError):
    """The picked inputs cannot run the requested output."""


class ReviewAssistantInputs(BaseModel):
    """The files picked for each input, by ID."""

    reviewed_draft: Optional[str] = Field(
        default=None, description="The draft the reviewers read"
    )
    revised_draft: Optional[str] = Field(
        default=None, description="The draft that addresses the reviewers' points"
    )
    reviewer_memos: list[str] = Field(default_factory=list)
    response_memos: list[str] = Field(default_factory=list)

    def by_slot(self) -> dict[ReviewInputSlot, list[str]]:
        """Every filled slot and its file IDs."""
        slots: dict[ReviewInputSlot, list[str]] = {
            ReviewInputSlot.REVIEWED_DRAFT: (
                [self.reviewed_draft] if self.reviewed_draft else []
            ),
            ReviewInputSlot.REVISED_DRAFT: (
                [self.revised_draft] if self.revised_draft else []
            ),
            ReviewInputSlot.REVIEWER_MEMOS: self.reviewer_memos,
            ReviewInputSlot.RESPONSE_MEMOS: self.response_memos,
        }
        return {slot: ids for slot, ids in slots.items() if ids}


class ReviewAssistantRun(BaseModel):
    """A review-assistant run with the inputs it was handed and its report."""

    run: WorkflowRunPublic
    input_files: dict[str, list[str]]
    report_html: Optional[str] = None


def _check_slots(
    output: WorkflowRunType, slots: dict[ReviewInputSlot, list[str]]
) -> None:
    spec = REVIEW_OUTPUT_SPECS.get(output)
    if spec is None:
        raise ReviewInputsError(f"{output.value} is not a review-assistant output")
    missing = [slot.value for slot in spec.required if slot not in slots]
    if missing:
        raise ReviewInputsError(f"Missing required inputs: {', '.join(missing)}")
    unexpected = [slot.value for slot in slots if slot not in spec.accepted]
    if unexpected:
        raise ReviewInputsError(
            f"{output.value} does not take these inputs: {', '.join(unexpected)}"
        )
    all_ids = [file_id for ids in slots.values() for file_id in ids]
    if len(set(all_ids)) != len(all_ids):
        raise ReviewInputsError("A file can fill only one input, once")


async def _assert_files_in_project(project_id: str, file_ids: list[str]) -> None:
    try:
        ids = [uuid.UUID(file_id) for file_id in file_ids]
    except ValueError as e:
        raise ReviewInputsError(f"Invalid file ID: {e}") from e
    async with get_async_db_session() as session:
        stmt = select(col(File.id)).where(
            col(File.project_id) == uuid.UUID(project_id),
            col(File.id).in_(ids),
            col(File.role).in_(_PICKABLE_ROLES),
        )
        found = {str(file_id) for file_id in (await session.execute(stmt)).scalars()}
    absent = [file_id for file_id in file_ids if str(uuid.UUID(file_id)) not in found]
    if absent:
        raise ReviewInputsError(
            f"These files are not documents of this project: {', '.join(absent)}"
        )


async def resolve_input_files(
    project_id: str, output: WorkflowRunType, inputs: ReviewAssistantInputs
) -> dict[str, list[str]]:
    """Validate the picked inputs for ``output`` and return its ``input_files``.

    Raises:
        ReviewInputsError: a required input is missing, an input the output
            does not read is filled, a file fills two inputs, or a file is not
            one of the project's documents.
    """
    slots = inputs.by_slot()
    _check_slots(output, slots)
    await _assert_files_in_project(
        project_id, [file_id for ids in slots.values() for file_id in ids]
    )
    return {slot.value: ids for slot, ids in slots.items()}


async def seed_run_inputs(
    run_ids: list[str],
    project_id: str,
    output: WorkflowRunType,
    input_files: dict[str, list[str]],
    model: Optional[str],
) -> str:
    """Record the inputs on the new run of ``output`` and return its ID.

    A run's state is first written when it starts executing, which can be a
    while after it is created (it waits on document processing). Seeding it
    with the run's config now is what lets the page list a pending run with
    the inputs it was started on; the runner overwrites it with the same
    config when it starts.
    """
    for run_id in run_ids:
        run = await get_workflow_run(run_id)
        if run.type != output:
            continue
        config = SimpleDeepAgentConfig(
            type=output, project_id=project_id, model=model, input_files=input_files
        )
        await persist_workflow_run_state(
            run_id, SimpleDeepAgentState(type=output, config=config)
        )
        return run_id
    raise RuntimeError(f"No {output.value} run was created")


async def list_review_assistant_runs(
    project_id: str, output: WorkflowRunType
) -> list[ReviewAssistantRun]:
    """Runs of ``output`` that were handed their inputs, newest first, across
    every revision."""
    runs = await get_project_workflow_runs_by_type(
        project_id, output, revision=None, include_state=True
    )
    listed: list[ReviewAssistantRun] = []
    for run in runs:
        state = hydrate_workflow_run_state(run)
        if not isinstance(state, SimpleDeepAgentState) or not state.config.input_files:
            continue
        listed.append(
            ReviewAssistantRun(
                run=WorkflowRunPublic.model_validate(run),
                input_files=state.config.input_files,
                report_html=state.result.report_html if state.result else None,
            )
        )
    return listed
