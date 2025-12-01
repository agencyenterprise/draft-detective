import logging
from typing import TYPE_CHECKING

from lib.services.docx_manipulator import DocxComment, docx_manipulator_service
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

if TYPE_CHECKING:
    from lib.workflows.runtime import ContextSchema, Runtime

logger = logging.getLogger(__name__)


@register_node(
    name="generate_docx_output",
    description="Generate a reviewed DOCX file with AI comments",
)
async def generate_docx_output(
    state: ClaimSubstantiatorState,
    runtime: "Runtime[ContextSchema]",
) -> ClaimSubstantiatorState:
    """
    Generate a DOCX file with AI-generated comments if the original file was .docx
    """

    # Check if original file was a docx
    if not state.file.original_file_path:
        logger.info("No original docx file, skipping docx output generation")
        return {}

    if not state.file.original_file_path.endswith(".docx"):
        logger.info("Original file was not .docx, skipping docx output generation")
        return {}

    if not state.workflow_run_id:
        logger.warning("No workflow_run_id available, skipping docx output generation")
        return {}

    try:
        # Collect comments from analysis results
        comments = []
        for chunk in state.chunks:
            if chunk.unsupported_claims:
                for claim in chunk.unsupported_claims:
                    comments.append(
                        DocxComment(
                            chunk_index=chunk.chunk_index,
                            text=chunk.content,
                            comment_text=f"Unsupported claim: {claim.claim}",
                        )
                    )

            if chunk.inferences:
                for inference in chunk.inferences:
                    comments.append(
                        DocxComment(
                            chunk_index=chunk.chunk_index,
                            text=chunk.content,
                            comment_text=f"Inference detected: {inference.inference}",
                        )
                    )

        # Generate the reviewed docx
        processed_path = await docx_manipulator_service.add_comments_to_docx(
            original_docx_path=state.file.original_file_path,
            comments=comments,
            workflow_run_id=state.workflow_run_id,
        )

        logger.info(
            f"Generated reviewed docx at {processed_path} with {len(comments)} comments"
        )

        return {}

    except Exception as e:
        logger.error(f"Failed to generate docx output: {e}", exc_info=True)
        return {}
