"""Prepare comments and mapping inputs for DOCX generation."""

from typing import Dict

from langgraph.runtime import Runtime

from lib.services.docx.manipulator import issue_to_comment
from lib.services.share_links import get_resource_by_token
from lib.workflows.context import ContextSchema
from lib.workflows.docx_generation.state import DocxGenerationState
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.models import WorkflowRunType


async def prepare_docx_inputs(
    state: DocxGenerationState, runtime: Runtime[ContextSchema]
) -> DocxGenerationState:
    """
    Fetch the document processing run by project_id, load its full state, build comments,
    and prepare validated chunks for paragraph mapping. Share token is validated here.
    """
    from lib.services.issues import convert_to_issues
    from lib.services.workflow_runs import (
        get_project_workflow_run_by_type,
        get_project_workflow_runs,
        get_workflow_run_state_by_thread_id,
    )

    if not state.config.project_id:
        raise ValueError("project_id is required for DOCX generation workflow")

    doc_run = await get_project_workflow_run_by_type(
        state.config.project_id, WorkflowRunType.DOCUMENT_PROCESSING
    )
    if not doc_run:
        raise ValueError("No document processing workflow run found for this project")

    doc_state_raw = await get_workflow_run_state_by_thread_id(
        doc_run.langgraph_thread_id,
        WorkflowRunType.DOCUMENT_PROCESSING,
    )
    if not doc_state_raw:
        raise ValueError("Failed to load document processing state")

    if not isinstance(doc_state_raw, DocumentProcessingState):
        raise ValueError("State is not a DocumentProcessingState")

    doc_state: DocumentProcessingState = doc_state_raw

    if (
        not doc_state.file.original_file_path
        or not doc_state.file.original_file_path.endswith(".docx")
    ):
        raise ValueError("Original file must be a .docx to generate reviewed DOCX")

    share_token = state.config.share_token
    if share_token:
        share_link = await get_resource_by_token(share_token)
        if not share_link:
            raise ValueError("Invalid share token")
    chunk_content_map: Dict[int, str] = {
        c.chunk_index: c.content for c in doc_state.chunks
    }

    workflow_runs = await get_project_workflow_runs(state.config.project_id)
    workflow_states = [run.state for run in workflow_runs if run.state is not None]
    issues = convert_to_issues(workflow_states)

    comments = [
        c
        for issue in issues
        if (c := issue_to_comment(issue, chunk_content_map, share_token))
    ]

    base_name = doc_state.file.file_name.rsplit(".", 1)[0]

    return state.model_copy(
        update={
            "comments": comments,
            "chunks": doc_state.chunks,
            "original_file_path": doc_state.file.original_file_path,
            "base_file_name": base_name,
        }
    )
