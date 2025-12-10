import logging
from typing import Dict, Optional

from langgraph.runtime import Runtime

from lib.agents.models import DocumentMetadata, ValidatedDocument
from lib.services.docx_manipulator import (
    CommentSeverity,
    DocxComment,
    docx_manipulator_service,
)
from lib.workflows.claim_substantiation.nodes.rank_issues import rank_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SeverityEnum,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


def _map_severity(severity: SeverityEnum) -> CommentSeverity:
    """Map workflow SeverityEnum to CommentSeverity."""
    mapping = {
        SeverityEnum.HIGH: CommentSeverity.HIGH,
        SeverityEnum.MEDIUM: CommentSeverity.MEDIUM,
        SeverityEnum.LOW: CommentSeverity.LOW,
        SeverityEnum.NONE: CommentSeverity.NONE,
    }
    return mapping.get(severity, CommentSeverity.NONE)


def issue_to_comment(
    issue: DocumentIssue,
    chunk_content_map: Dict[int, str],
) -> Optional[DocxComment]:
    """Convert a DocumentIssue to a DocxComment."""
    if issue.chunk_index is None:
        return None

    chunk_content = chunk_content_map.get(issue.chunk_index, "")
    if not chunk_content:
        return None

    return DocxComment(
        chunk_index=issue.chunk_index,
        text=chunk_content,
        comment_text=f"{issue.title}\n\n{issue.description}",
        severity=_map_severity(issue.severity),
    )


@register_node(
    name="generate_docx_output",
    description="Generate a reviewed DOCX file with AI comments",
)
async def generate_docx_output(
    state: ClaimSubstantiatorState,
    runtime: Runtime[ContextSchema],
) -> ClaimSubstantiatorState:
    """
    Generate a DOCX file with AI-generated comments if the original file was .docx
    """

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
        chunk_content_map = {chunk.chunk_index: chunk.content for chunk in state.chunks}

        ranked_issues_result = rank_issues(state)
        ranked_issues = ranked_issues_result.get("ranked_issues", [])

        comments = [
            comment
            for issue in ranked_issues
            if (comment := issue_to_comment(issue, chunk_content_map))
        ]

        validated_chunks = [
            ValidatedDocument(
                page_content=chunk.content,
                metadata=DocumentMetadata(
                    chunk_index=chunk.chunk_index,
                    paragraph_index=chunk.paragraph_index,
                    chunk_index_within_paragraph=0,  # Not used for mapping
                ),
            )
            for chunk in state.chunks
        ]

        # Generate the reviewed docx
        processed_path = await docx_manipulator_service.add_comments_to_docx(
            original_docx_path=state.file.original_file_path,
            comments=comments,
            workflow_run_id=state.workflow_run_id,
            chunks=validated_chunks,
        )

        logger.info(
            f"Generated reviewed docx at {processed_path} with {len(comments)} comments"
        )

        return {}

    except Exception as e:
        logger.error(f"Failed to generate docx output: {e}", exc_info=True)
        return {}
