import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from lib.agents.claim_extractor import Claim, ClaimResponseWithChunkIndex
from lib.agents.claim_extractor_v2 import (
    ClaimExtractorV2Agent,
    ClaimResponseV2,
    ClaimV2,
)
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.services.chunk_line_matcher import find_chunks_by_fuzzy_match
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.claim_extraction_v2.state import ClaimExtractionV2State
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError
from lib.services.file_artifacts_service.types import FileArtifactsServiceType

logger = logging.getLogger(__name__)


class ParagraphContext(BaseModel):
    """Structured context for a single paragraph including section metadata."""

    paragraph_index: int = Field(description="Zero-based index of the paragraph")
    paragraph_text: str = Field(description="Full text content of the paragraph")
    headings: Optional[List[str]] = Field(
        default=None,
        description="Section headings hierarchy for this paragraph",
    )
    word_count: int = Field(description="Word count of the paragraph text")


def _build_paragraph_contexts(
    chunks: List[AnalyzedChunk],
    file_artifacts_service: FileArtifactsServiceType,
) -> List[ParagraphContext]:
    """Build an ordered list of ParagraphContext objects.

    Uses only unique paragraph indices seen in chunks, preserving order.
    Includes section heading metadata from chunk data.
    """
    seen: set[int] = set()
    paragraphs: List[ParagraphContext] = []
    for chunk in chunks:
        if chunk.paragraph_index not in seen:
            seen.add(chunk.paragraph_index)
            text = file_artifacts_service.get_paragraph_text(
                chunks, chunk.paragraph_index
            )
            if text.strip():
                paragraphs.append(
                    ParagraphContext(
                        paragraph_index=chunk.paragraph_index,
                        paragraph_text=text,
                        headings=chunk.headings,
                        word_count=len(text.split()),
                    )
                )
    return paragraphs


def _batch_paragraphs_by_word_limit(
    paragraphs: List[ParagraphContext],
    word_limit: int,
) -> List[List[ParagraphContext]]:
    """Group consecutive paragraphs into batches under the word limit.

    Each batch is a list of ParagraphContext objects.
    A single paragraph exceeding the limit gets its own batch.
    """
    batches: List[List[ParagraphContext]] = []
    current_batch: List[ParagraphContext] = []
    current_word_count = 0

    for para in paragraphs:
        if current_batch and current_word_count + para.word_count > word_limit:
            batches.append(current_batch)
            current_batch = []
            current_word_count = 0

        current_batch.append(para)
        current_word_count += para.word_count

    if current_batch:
        batches.append(current_batch)

    return batches


def _format_heading_path(headings: Optional[List[str]]) -> str:
    """Format a heading list as a readable path string."""
    if not headings:
        return ""
    return " > ".join(headings)


def _format_batch_text(batch: List[ParagraphContext]) -> str:
    """Serialize a batch of paragraphs with heading transition markers.

    Heading markers are emitted only when the heading path changes from the
    previous paragraph in the batch. This keeps the payload compact while
    preserving section context for the extraction agent.
    """
    sections: List[str] = []
    prev_heading_path: Optional[str] = None

    for para in batch:
        current_heading_path = _format_heading_path(para.headings)

        # Emit heading marker only on transitions
        if current_heading_path != prev_heading_path:
            if current_heading_path:
                sections.append(f"[Section: {current_heading_path}]")
            prev_heading_path = current_heading_path

        sections.append(para.paragraph_text)

    return "\n\n".join(sections)


def _adapt_v2_claim_to_v1(claim_v2: ClaimV2) -> Claim:
    """Map a ClaimV2 to a v1 Claim for downstream compatibility."""
    return Claim(
        text=claim_v2.key_sentence,
        claim=claim_v2.claim,
        rationale=claim_v2.rationale,
        central=claim_v2.central,
        centrality_rationale=claim_v2.centrality_rationale,
        needs_external_verification=claim_v2.needs_external_verification,
    )


def _build_claims_with_chunk_indices(
    v2_response: ClaimResponseV2,
    chunks: List[AnalyzedChunk],
    workflow_run_id: str | None = None,
) -> Tuple[List[ClaimResponseWithChunkIndex], List[WorkflowError]]:
    """Map v2 claims to ClaimResponseWithChunkIndex using fuzzy matching.

    For each ClaimV2, find the chunk(s) its key_sentence came from using
    find_chunks_by_fuzzy_match, then build one ClaimResponseWithChunkIndex
    per chunk that had at least one matching claim.

    Returns:
        Tuple of (matched claim responses, errors for unmatched claims).
        Unmatched claims are NOT attached to any chunk.
    """
    # Map: chunk_index -> list of v1 Claims
    claims_by_chunk: Dict[int, List[Claim]] = defaultdict(list)
    errors: List[WorkflowError] = []

    for claim_v2 in v2_response.claims:
        v1_claim = _adapt_v2_claim_to_v1(claim_v2)
        matched_indices = find_chunks_by_fuzzy_match(chunks, claim_v2.key_sentence)

        if matched_indices:
            for chunk_index in matched_indices:
                claims_by_chunk[chunk_index].append(v1_claim)
        else:
            logger.warning(
                "Unmatched v2 claim (no chunk found): key_sentence=%r, claim=%r",
                claim_v2.key_sentence,
                claim_v2.claim,
            )
            errors.append(
                WorkflowError(
                    task_name="extract_claims_v2",
                    error=(
                        f"Could not match claim to any chunk via fuzzy match. "
                        f"key_sentence: {claim_v2.key_sentence!r}"
                    ),
                    workflow_run_id=workflow_run_id,
                )
            )

    # Build one ClaimResponseWithChunkIndex per chunk
    results: List[ClaimResponseWithChunkIndex] = []
    for chunk_index in sorted(claims_by_chunk.keys()):
        results.append(
            ClaimResponseWithChunkIndex(
                chunk_index=chunk_index,
                claims=claims_by_chunk[chunk_index],
                rationale=v2_response.rationale,
            )
        )

    return results, errors


async def _extract_batch_claims(
    agent: ClaimExtractorV2Agent,
    batch: List[ParagraphContext],
    chunks: List[AnalyzedChunk],
    workflow_run_id: str | None = None,
) -> Tuple[List[ClaimResponseWithChunkIndex], List[WorkflowError]]:
    """Extract claims from a single paragraph-group batch."""
    batch_text = _format_batch_text(batch)
    v2_response = await agent.ainvoke({"text": batch_text})
    return _build_claims_with_chunk_indices(v2_response, chunks, workflow_run_id)


@register_node(
    "Extract claims (v2)",
    "Extract claims from paragraph groups using v2 agent",
)
async def extract_claims_v2(
    state: ClaimExtractionV2State, runtime: Runtime[ContextSchema]
) -> Dict[str, Any]:
    agent = ClaimExtractorV2Agent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Get chunks
    chunks = await file_artifacts_service.get_chunks()

    # Build paragraph contexts and batch by word limit
    paragraphs = _build_paragraph_contexts(chunks, file_artifacts_service)
    word_limit = state.config.paragraph_group_word_limit
    batches = _batch_paragraphs_by_word_limit(paragraphs, word_limit)

    logger.info(
        "extract_claims_v2: %d paragraphs in %d batches (word_limit=%d)",
        len(paragraphs),
        len(batches),
        word_limit,
    )

    # Log representative heading paths per batch for observability
    for batch_idx, batch in enumerate(batches):
        heading_paths = [
            _format_heading_path(p.headings) or "(no headings)" for p in batch
        ]
        unique_paths = list(dict.fromkeys(heading_paths))
        logger.debug(
            "  batch %d: %d paragraphs, sections=%s",
            batch_idx,
            len(batch),
            unique_paths[:3],
        )

    workflow_run_id = runtime.context.workflow_run_id

    # Extract claims for each batch in parallel
    tasks = [
        _extract_batch_claims(agent, batch, chunks, workflow_run_id)
        for batch in batches
    ]
    results = await run_tasks(tasks, desc="Extracting claims (v2)")
    batch_results, exceptions = results

    # Collect exception-based errors
    batch_indices = list(range(len(batches)))
    errors = convert_exceptions_to_workflow_errors(
        "_extract_batch_claims",
        exceptions,
        batch_indices,
        workflow_run_id=workflow_run_id,
    )

    # Flatten all claim responses and unmatched-claim errors from all batches
    all_claims: List[ClaimResponseWithChunkIndex] = []
    for batch_result in batch_results:
        if batch_result is not None:
            matched_claims, unmatched_errors = batch_result
            all_claims.extend(matched_claims)
            errors.extend(unmatched_errors)

    return {
        "claims": all_claims,
        "errors": errors,
    }
