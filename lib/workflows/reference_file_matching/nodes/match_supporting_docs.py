"""Node for matching references to supporting documents.

Uses a two-stage approach for scalability:
1. Embedding-based candidate retrieval (fast, handles 300+ documents)
2. Batched LLM verification (accurate, processes 5 references per call)
"""

import logging

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.batched_reference_matcher import (
    REFERENCES_PER_BATCH,
    BatchedReferenceMatcherAgent,
)
from lib.run_utils import run_tasks
from lib.services.references.embedding_matcher import (
    CandidateMatch,
    ReferenceEmbeddingMatcher,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_summarization.state import FileSummary
from lib.workflows.reference_file_matching.state import (
    MatchSource,
    ReferenceFileMatch,
    ReferenceFileMatchingState,
)

logger = logging.getLogger(__name__)

MAX_CONCURRENT_BATCHES = 5


async def _retrieve_candidates(
    reference_texts: list[str],
    summaries: list[FileSummary],
    context: ContextSchema,
    top_k: int = 15,
) -> list[list[CandidateMatch]]:
    matcher = ReferenceEmbeddingMatcher(
        context.openai_api_key or "",
        workflow_run_id=context.workflow_run_id,
        project_id=context.project_id,
    )
    await matcher.index_summaries(summaries)
    return await matcher.find_candidates(reference_texts, top_k=top_k)


def _resolve_match(
    match_candidate: str,
    candidates: list[CandidateMatch],
) -> str | None:
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
    batch_refs: list[str],
    batch_candidates: list[list[CandidateMatch]],
    agent: BatchedReferenceMatcherAgent,
    config,
) -> list[str | None]:
    """Process a batch of references and return matched file_ids."""
    try:
        result = await agent.match_batch(batch_refs, batch_candidates, config=config)

        results: list[str | None] = [None] * len(batch_refs)
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
    reference_texts: list[str],
    summaries: list[FileSummary],
    context: ContextSchema,
) -> list[str | None]:
    """Run two-stage matching and return list of matched file_ids (None if no match)."""
    logger.info("Stage 1: Retrieving candidates via embedding similarity")
    candidates_per_ref = await _retrieve_candidates(reference_texts, summaries, context)

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
    all_results: list[str | None] = []
    for i, batch_result in enumerate(batch_results):
        if batch_result is None:
            start_idx = i * REFERENCES_PER_BATCH
            end_idx = min(start_idx + REFERENCES_PER_BATCH, len(reference_texts))
            all_results.extend([None] * (end_idx - start_idx))
        else:
            all_results.extend(batch_result)

    return all_results


@register_node("Match references to supporting documents")
async def match_supporting_docs_node(
    state: ReferenceFileMatchingState, runtime: Runtime[ContextSchema]
) -> dict:
    """Match extracted references to supporting documents.

    Two-stage approach:
    1. Embedding-based candidate retrieval (top-15 per reference)
    2. Batched LLM verification (5 references per call)
    """
    # Get extracted references from the reference extraction workflow
    extracted_references = (
        await runtime.context.file_artifacts_service.get_extracted_references()
    )

    if not extracted_references:
        logger.info("No extracted references to match")
        return {"matches": state.matches}

    # Skip references that already have a match (manual or automatic)
    already_matched_ids = {match.reference_id for match in state.matches}
    unmatched_references = [
        ref for ref in extracted_references if ref.id not in already_matched_ids
    ]

    if not unmatched_references:
        logger.info("All references already matched, skipping matching")
        return {"matches": state.matches}

    logger.info(
        f"{len(already_matched_ids)} references already matched, "
        f"{len(unmatched_references)} remaining to match"
    )

    # Build summaries list for supporting documents
    summaries: list[FileSummary] = [
        await runtime.context.file_artifacts_service.get_file_summary(file_id)
        for file_id in state.supporting_file_ids
    ]

    # Extract reference texts for matching
    reference_texts = [ref.text for ref in unmatched_references]

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

    # Build ReferenceFileMatch objects only for newly matched references
    new_matches: list[ReferenceFileMatch] = []
    matched_count = 0

    for ref, file_id in zip(unmatched_references, match_results):
        if file_id is not None:
            matched_count += 1
            new_matches.append(
                ReferenceFileMatch(
                    reference_id=ref.id,
                    file_id=file_id,
                    source=MatchSource.AUTO_MATCHED,
                )
            )

    logger.info(
        f"Matched {matched_count}/{len(unmatched_references)} remaining references to documents"
    )

    return {"matches": state.matches + new_matches}
