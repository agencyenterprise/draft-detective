"""Node for matching references to supporting documents.

Uses a two-stage approach for scalability:
1. Embedding-based candidate retrieval (fast, handles 300+ documents)
2. Batched LLM verification (accurate, processes 5 references per call)
"""

import logging
from typing import List, Optional

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.batched_reference_matcher import (
    REFERENCES_PER_BATCH,
    BatchedReferenceMatcherAgent,
)
from lib.run_utils import run_tasks
from lib.workflows.document_processing.state import FileSummary
from lib.services.reference_embedding_matcher import (
    CandidateMatch,
    ReferenceEmbeddingMatcher,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ExtractedReference
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatch,
    ReferenceFileMatchingState,
)

logger = logging.getLogger(__name__)

MAX_CONCURRENT_BATCHES = 5


async def _retrieve_candidates(
    reference_texts: List[str],
    summaries: List[FileSummary],
    openai_api_key: str,
    top_k: int = 15,
) -> List[List[CandidateMatch]]:
    matcher = ReferenceEmbeddingMatcher(openai_api_key)
    await matcher.index_summaries(summaries)
    return await matcher.find_candidates(reference_texts, top_k=top_k)


def _resolve_match(
    match_candidate: str,
    candidates: List[CandidateMatch],
) -> Optional[str]:
    """Map LLM's letter response (A/B/C) back to file_id."""
    if match_candidate == "NONE" or not candidates:
        return None

    try:
        cand_idx = ord(match_candidate.upper()) - ord("A")
        if 0 <= cand_idx < len(candidates):
            return candidates[cand_idx].file_id
    except (ValueError, IndexError):
        pass

    return None


async def _process_batch(
    batch_refs: List[str],
    batch_candidates: List[List[CandidateMatch]],
    agent: BatchedReferenceMatcherAgent,
    config,
) -> List[Optional[str]]:
    """Process a batch of references and return matched file_ids."""
    try:
        result = await agent.match_batch(batch_refs, batch_candidates, config=config)

        results: List[Optional[str]] = [None] * len(batch_refs)
        for match in result.matches:
            if 0 <= match.reference_index < len(batch_refs):
                results[match.reference_index] = _resolve_match(
                    match.matched_candidate,
                    batch_candidates[match.reference_index],
                )
        return results

    except Exception as e:
        logger.warning(f"Batch matching failed: {e}")
        return [None] * len(batch_refs)


async def _two_stage_match(
    reference_texts: List[str],
    summaries: List[FileSummary],
    context: ContextSchema,
) -> List[Optional[str]]:
    """Run two-stage matching and return list of matched file_ids (None if no match)."""
    logger.info("Stage 1: Retrieving candidates via embedding similarity")
    candidates_per_ref = await _retrieve_candidates(
        reference_texts, summaries, context.openai_api_key or ""
    )

    logger.info(f"Stage 2: LLM verification in batches of {REFERENCES_PER_BATCH}")
    agent = BatchedReferenceMatcherAgent(context)
    config = ensure_config()

    tasks = [
        _process_batch(
            reference_texts[i : i + REFERENCES_PER_BATCH],
            candidates_per_ref[i : i + REFERENCES_PER_BATCH],
            agent,
            config,
        )
        for i in range(0, len(reference_texts), REFERENCES_PER_BATCH)
    ]

    batch_results, _ = await run_tasks(
        tasks, desc="Matching references", max_concurrent=MAX_CONCURRENT_BATCHES
    )

    # Flatten results, treating failed batches as no-matches
    all_results: List[Optional[str]] = []
    for i, batch_result in enumerate(batch_results):
        if batch_result is None:
            start_idx = i * REFERENCES_PER_BATCH
            end_idx = min(start_idx + REFERENCES_PER_BATCH, len(reference_texts))
            all_results.extend([None] * (end_idx - start_idx))
        else:
            all_results.extend(batch_result)

    return all_results


@register_node(
    "Match references to supporting documents",
    "Match extracted references to user-provided supporting documents using two-stage approach",
)
async def match_supporting_docs_node(
    state: ReferenceFileMatchingState, runtime: Runtime[ContextSchema]
) -> dict:
    """Match extracted references to supporting documents.

    Two-stage approach:
    1. Embedding-based candidate retrieval (top-15 per reference)
    2. Batched LLM verification (5 references per call)
    """
    # Get extracted references from the reference extraction workflow
    extracted_references: List[ExtractedReference] = (
        await runtime.context.file_artifacts_service.get_extracted_references()
    )

    if not extracted_references:
        logger.info("No extracted references to match")
        return {"matches": []}

    # Build summaries list for supporting documents
    summaries: List[FileSummary] = [
        await runtime.context.file_artifacts_service.get_file_summary(file_id)
        for file_id in state.supporting_file_ids
    ]

    # Extract reference texts for matching
    reference_texts = [ref.text for ref in extracted_references]

    logger.info(
        f"Matching {len(reference_texts)} references "
        f"against {len(summaries)} document summaries"
    )

    if summaries:
        match_results = await _two_stage_match(
            reference_texts, summaries, runtime.context
        )
    else:
        match_results = [None] * len(reference_texts)

    # Build ReferenceFileMatch objects only for matched references
    matches: List[ReferenceFileMatch] = []
    matched_count = 0

    for ref, file_id in zip(extracted_references, match_results):
        if file_id is not None:
            matched_count += 1
            matches.append(ReferenceFileMatch(reference_id=ref.id, file_id=file_id))

    logger.info(
        f"Matched {matched_count}/{len(extracted_references)} references to documents"
    )

    return {"matches": matches}
