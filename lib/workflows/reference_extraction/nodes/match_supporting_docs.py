"""Node for matching references to supporting documents.

Uses a two-stage approach for scalability:
1. Embedding-based candidate retrieval (fast, handles 300+ documents)
2. Batched LLM verification (accurate, processes 5 references per call)
"""

import logging
from typing import Dict, List, Optional, Tuple

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.batched_reference_matcher import (
    REFERENCES_PER_BATCH,
    BatchedReferenceMatcherAgent,
)
from lib.agents.document_summarizer import DocumentSummary
from lib.models.bibliography_item import BibliographyItem
from lib.run_utils import run_tasks
from lib.services.file import FileDocument
from lib.services.reference_embedding_matcher import (
    CandidateMatch,
    ReferenceEmbeddingMatcher,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ReferenceExtractionState

logger = logging.getLogger(__name__)

MAX_CONCURRENT_BATCHES = 5


async def _retrieve_candidates(
    reference_texts: List[str],
    summaries: Dict[int, DocumentSummary],
    openai_api_key: str,
    top_k: int = 15,
) -> List[List[CandidateMatch]]:
    matcher = ReferenceEmbeddingMatcher(openai_api_key)
    await matcher.index_summaries(summaries)
    return await matcher.find_candidates(reference_texts, top_k=top_k)


def _resolve_match(
    match_candidate: str,
    candidates: List[CandidateMatch],
    supporting_files: List[FileDocument],
) -> Tuple[int, str, Optional[str]]:
    """Map LLM's letter response (A/B/C) back to file index, name, and file_id."""
    if match_candidate == "NONE" or not candidates:
        return (-1, "", None)

    try:
        cand_idx = ord(match_candidate.upper()) - ord("A")
        if 0 <= cand_idx < len(candidates):
            doc_idx = candidates[cand_idx].doc_index
            if doc_idx < len(supporting_files):
                file_doc = supporting_files[doc_idx]
                # We need to return the document index + 1 because the index starts at 1
                return (doc_idx + 1, file_doc.file_name, file_doc.file_id)
    except (ValueError, IndexError):
        pass

    return (-1, "", None)


async def _process_batch(
    batch_refs: List[str],
    batch_candidates: List[List[CandidateMatch]],
    supporting_files: List[FileDocument],
    agent: BatchedReferenceMatcherAgent,
    config,
) -> List[Tuple[int, str, Optional[str]]]:
    try:
        result = await agent.match_batch(batch_refs, batch_candidates, config=config)

        # We need to map results back to document indices to return the correct document index, name, and file_id
        results: List[Tuple[int, str, Optional[str]]] = [(-1, "", None)] * len(
            batch_refs
        )
        for match in result.matches:
            if 0 <= match.reference_index < len(batch_refs):
                results[match.reference_index] = _resolve_match(
                    match.matched_candidate,
                    batch_candidates[match.reference_index],
                    supporting_files,
                )
        return results

    except Exception as e:
        logger.warning(f"Batch matching failed: {e}")
        return [(-1, "", None)] * len(batch_refs)


async def _two_stage_match(
    reference_texts: List[str],
    summaries: Dict[int, DocumentSummary],
    supporting_files: List[FileDocument],
    context: ContextSchema,
) -> List[Tuple[int, str, Optional[str]]]:
    logger.info("Stage 1: Retrieving candidates via embedding similarity")
    candidates_per_ref = await _retrieve_candidates(
        reference_texts, summaries, context.openai_api_key
    )

    logger.info(f"Stage 2: LLM verification in batches of {REFERENCES_PER_BATCH}")
    agent = BatchedReferenceMatcherAgent(context)
    config = ensure_config()

    tasks = [
        _process_batch(
            reference_texts[i : i + REFERENCES_PER_BATCH],
            candidates_per_ref[i : i + REFERENCES_PER_BATCH],
            supporting_files,
            agent,
            config,
        )
        for i in range(0, len(reference_texts), REFERENCES_PER_BATCH)
    ]

    batch_results, _ = await run_tasks(
        tasks, desc="Matching references", max_concurrent=MAX_CONCURRENT_BATCHES
    )

    # We need to flatten results, treating failed batches as no-matches
    all_results: List[Tuple[int, str, Optional[str]]] = []
    for i, batch_result in enumerate(batch_results):
        if batch_result is None:
            start_idx = i * REFERENCES_PER_BATCH
            end_idx = min(start_idx + REFERENCES_PER_BATCH, len(reference_texts))
            all_results.extend([(-1, "", None)] * (end_idx - start_idx))
        else:
            all_results.extend(batch_result)

    return all_results


@register_node(
    "Match references to supporting documents",
    "Match extracted references to user-provided supporting documents using two-stage approach",
)
async def match_supporting_docs_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """Match extracted references to supporting documents.

    Two-stage approach:
    1. Embedding-based candidate retrieval (top-15 per reference)
    2. Batched LLM verification (5 references per call)
    """
    extracted_reference_texts = state.extracted_reference_texts
    summaries = state.supporting_documents_summaries or {}
    supporting_files = state.supporting_files or []

    if not extracted_reference_texts:
        logger.info("No extracted reference texts to match")
        return {"references": []}

    logger.info(
        f"Matching {len(extracted_reference_texts)} references "
        f"against {len(summaries)} document summaries"
    )

    if summaries and supporting_files:
        match_results = await _two_stage_match(
            extracted_reference_texts, summaries, supporting_files, runtime.context
        )
    else:
        match_results = [(-1, "", None) for _ in extracted_reference_texts]

    # We need to build bibliography items to return the correct bibliography items
    references: List[BibliographyItem] = []
    matched_count = 0

    for ref_text, (match_index, match_name, match_file_id) in zip(
        extracted_reference_texts, match_results
    ):
        if match_index > 0:
            matched_count += 1

        references.append(
            BibliographyItem(
                text=ref_text,
                has_associated_supporting_document=match_index > 0,
                index_of_associated_supporting_document=match_index,
                name_of_associated_supporting_document=match_name,
                file_id=match_file_id,
            )
        )

    logger.info(f"Matched {matched_count}/{len(references)} references to documents")

    return {"references": references}
