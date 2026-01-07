"""Node to write DOCX using prepared comments and chunks."""

import os

from langgraph.runtime import Runtime

from lib.services.docx.manipulator import docx_manipulator_service
from lib.workflows.context import ContextSchema
from lib.workflows.docx_generation.state import DocxGenerationState


async def generate_docx(
    state: DocxGenerationState, runtime: Runtime[ContextSchema]
) -> DocxGenerationState:
    """
    Final step: map prepared chunks to paragraphs and write the DOCX with comments.
    """

    from lib.services.docx_workflow_service import get_cache_key

    if not state.comments or not state.chunks:
        raise ValueError("Comments and chunks must be prepared before writing DOCX")

    if not state.original_file_path:
        raise ValueError("Original file path is required to generate DOCX")

    if not state.config.project_id:
        raise ValueError("project_id is required for DOCX generation workflow")

    output_id = get_cache_key(state.config.project_id, state.config.share_token)

    output_path = await docx_manipulator_service.add_comments_to_docx(
        original_docx_path=state.original_file_path,
        comments=state.comments,
        workflow_run_id=output_id,
        chunks=state.chunks,
    )

    filename = f"{state.base_file_name}_reviewed.docx"

    return state.model_copy(
        update={
            "generated_file_path": output_path,
            "filename": filename,
        }
    )
