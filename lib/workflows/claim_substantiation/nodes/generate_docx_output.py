import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from lib.agents.models import DocumentMetadata, ValidatedDocument
from lib.services.docx_manipulator import DocxComment, docx_manipulator_service
from lib.workflows.claim_substantiation.nodes.rank_issues import rank_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SeverityEnum,
)
from lib.workflows.decorators import register_node

if TYPE_CHECKING:
    from lib.workflows.runtime import ContextSchema, Runtime

logger = logging.getLogger(__name__)


def get_severity_icon(severity: SeverityEnum) -> str:
    """Get icon for a severity level."""
    match severity:
        case SeverityEnum.HIGH:
            return "⚠️"
        case SeverityEnum.MEDIUM:
            return "⚡"
        case SeverityEnum.LOW:
            return "ℹ️"
        case _:
            return "📝"


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

    icon = get_severity_icon(issue.severity)
    return DocxComment(
        chunk_index=issue.chunk_index,
        text=chunk_content,
        comment_text=f"{icon} {issue.title}\n{issue.description}",
    )


def build_citation_suggestion_comments(
    state: ClaimSubstantiatorState,
) -> List[DocxComment]:
    """Build comments for citation suggestions (not included in rank_issues)."""
    from lib.agents.citation_suggester import RecommendedAction

    actionable_actions = {
        RecommendedAction.ADD_NEW_CITATION,
        RecommendedAction.REPLACE_EXISTING_REFERENCE,
        RecommendedAction.CITE_EXISTING_REFERENCE_IN_NEW_PLACE,
    }

    comments = []

    for chunk in state.chunks:
        for suggestion in chunk.citation_suggestions:
            actionable_refs = [
                ref
                for ref in (suggestion.relevant_references or [])
                if ref.recommended_action in actionable_actions
            ]
            if actionable_refs:
                ref_summary = "\n".join(
                    f"  • {ref.title} ({ref.recommended_action.value})"
                    for ref in actionable_refs[:3]
                )
                comments.append(
                    DocxComment(
                        chunk_index=chunk.chunk_index,
                        text=chunk.content,
                        comment_text=(
                            f"💡 Citation suggestion:\n"
                            f"{suggestion.rationale}\n\n"
                            f"Consider these references:\n{ref_summary}"
                        ),
                    )
                )

    return comments


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

        comments = []
        for issue in ranked_issues:
            if comment := issue_to_comment(issue, chunk_content_map):
                comments.append(comment)

        comments.extend(build_citation_suggestion_comments(state))

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
