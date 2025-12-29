"""Prepare comments and mapping inputs for DOCX generation."""

from typing import Dict

from langgraph.runtime import Runtime

from lib.services.docx.manipulator import issue_to_comment
from lib.services.share_links import get_resource_by_token
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.context import ContextSchema
from lib.workflows.docx_generation.state import DocxGenerationState
from lib.workflows.base import WorkflowRunType


async def prepare_docx_inputs(
    state: DocxGenerationState, runtime: Runtime[ContextSchema]
) -> DocxGenerationState:
    """
    Fetch the claim substantiation run, load its full state, build comments,
    and prepare validated chunks for paragraph mapping. Share token is validated here.
    """
    claim_run_id = state.config.claim_substantiation_run_id

    from lib.services.issues import convert_to_issues
    from lib.services.workflow_runs import (
        get_project_workflow_runs,
        get_workflow_run,
        get_workflow_run_state_by_thread_id,
    )

    claim_run = await get_workflow_run(claim_run_id)
    if claim_run.type != WorkflowRunType.CLAIM_SUBSTANTIATION:
        raise ValueError("Provided workflow run is not a claim substantiation run")

    claim_state: ClaimSubstantiatorState = await get_workflow_run_state_by_thread_id(
        claim_run.langgraph_thread_id,
        WorkflowRunType.CLAIM_SUBSTANTIATION,
    )

    if (
        not claim_state.file.original_file_path
        or not claim_state.file.original_file_path.endswith(".docx")
    ):
        raise ValueError("Original file must be a .docx to generate reviewed DOCX")

    share_token = state.config.share_token
    if share_token:
        share_link = await get_resource_by_token(share_token)
        if not share_link:
            raise ValueError("Invalid share token")
    chunk_content_map: Dict[int, str] = {
        c.chunk_index: c.content for c in claim_state.chunks
    }

    workflow_runs = await get_project_workflow_runs(state.config.project_id)
    workflow_states = [run.state for run in workflow_runs if run.state is not None]
    issues = convert_to_issues(workflow_states)

    comments = [
        c
        for issue in issues
        if (c := issue_to_comment(issue, chunk_content_map, share_token))
    ]

    base_name = claim_state.file.file_name.rsplit(".", 1)[0]

    return state.model_copy(
        update={
            "comments": comments,
            "chunks": claim_state.chunks,
            "original_file_path": claim_state.file.original_file_path,
            "base_file_name": base_name,
        }
    )
