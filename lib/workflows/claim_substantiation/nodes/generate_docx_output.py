import logging
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.services.docx_manipulator import DocxComment, docx_manipulator_service
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import register_node

if TYPE_CHECKING:
    from lib.workflows.runtime import ContextSchema, Runtime

logger = logging.getLogger(__name__)


class CommentConfig(BaseModel):
    """Configuration for generating a DOCX comment."""

    icon: str
    label: str
    reason: str
    suggestion: str


def get_alignment_config(alignment: EvidenceAlignmentLevel) -> Optional[CommentConfig]:
    """Get comment configuration for an evidence alignment level."""
    match alignment:
        case EvidenceAlignmentLevel.UNSUPPORTED:
            return CommentConfig(
                icon="⚠️",
                label="Unsupported claim",
                reason="Reason",
                suggestion="Suggestion",
            )
        case EvidenceAlignmentLevel.PARTIALLY_SUPPORTED:
            return CommentConfig(
                icon="⚡",
                label="Partially supported claim",
                reason="Reason",
                suggestion="Suggestion",
            )
        case EvidenceAlignmentLevel.UNVERIFIABLE:
            return CommentConfig(
                icon="❓",
                label="Unverifiable claim",
                reason="Reason",
                suggestion="Suggestion",
            )
        case _:
            return None


def build_comment(
    chunk_index: int,
    content: str,
    claim_text: str,
    config: CommentConfig,
    rationale: str,
    feedback: str,
) -> DocxComment:
    """Build a DocxComment from configuration and data."""
    return DocxComment(
        chunk_index=chunk_index,
        text=content,
        comment_text=(
            f"{config.icon} {config.label}: {claim_text}\n"
            f"{config.reason}: {rationale}\n"
            f"{config.suggestion}: {feedback}"
        ),
    )


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
        comments = []

        for chunk in state.chunks:
            claims_list = chunk.claims.claims if chunk.claims else []

            for substantiation in chunk.substantiations:
                config = get_alignment_config(substantiation.evidence_alignment)
                if config:
                    claim = (
                        claims_list[substantiation.claim_index]
                        if substantiation.claim_index < len(claims_list)
                        else None
                    )
                    comments.append(
                        build_comment(
                            chunk_index=chunk.chunk_index,
                            content=chunk.content,
                            claim_text=claim.claim if claim else "Unknown claim",
                            config=config,
                            rationale=substantiation.rationale,
                            feedback=substantiation.feedback,
                        )
                    )

            for validation in chunk.inference_validations:
                if not validation.valid:
                    claim = (
                        claims_list[validation.claim_index]
                        if validation.claim_index < len(claims_list)
                        else None
                    )
                    config = CommentConfig(
                        icon="⚠️",
                        label="Invalid inference",
                        reason="Reason",
                        suggestion="Suggestion",
                    )
                    comments.append(
                        build_comment(
                            chunk_index=chunk.chunk_index,
                            content=chunk.content,
                            claim_text=claim.claim if claim else "Unknown claim",
                            config=config,
                            rationale=validation.rationale,
                            feedback=validation.suggested_action,
                        )
                    )

            for suggestion in chunk.citation_suggestions:
                if actionable_refs := [
                    ref
                    for ref in (suggestion.relevant_references or [])
                    if ref.recommended_action
                    in ["add_citation", "replace_existing_reference"]
                ]:
                    ref_summary = "\n".join(
                        f"  • {ref.reference_title} ({ref.recommended_action})"
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

        from lib.agents.models import ValidatedDocument, DocumentMetadata

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
