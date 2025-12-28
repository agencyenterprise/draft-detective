"""Node for matching references to supporting documents.

Uses LLM-based matching with pre-computed document summaries for high accuracy.
"""

import asyncio
import logging
from typing import Dict, List

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.reference_matcher import ReferenceMatcherAgent
from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import ReferenceExtractionState

logger = logging.getLogger(__name__)

MAX_CONCURRENT_MATCHES = 10


def _format_candidate(idx: int, summary: DocumentSummary) -> str:
    """Format a document summary as a candidate for matching."""
    return (
        f"{idx}. Title: {summary.title}\n"
        f"   Authors: {summary.authors}\n"
        f"   Year: {summary.publication_date}"
    )


async def _match_reference(
    ref_text: str,
    summaries: Dict[int, DocumentSummary],
    supporting_files: List[FileDocument],
    context: ContextSchema,
) -> tuple[int, str]:
    """Match a single reference to available document summaries using LLM."""
    if not summaries:
        return (-1, "")

    candidates = "\n".join(
        _format_candidate(idx + 1, summary) for idx, summary in summaries.items()
    )

    agent = ReferenceMatcherAgent(context)
    config = ensure_config()

    try:
        result = await agent.ainvoke(
            {"reference_text": ref_text, "candidates": candidates},
            config=config,
        )

        if result.matched_index > 0 and result.matched_index <= len(summaries):
            doc_idx = result.matched_index - 1
            if doc_idx in summaries and doc_idx < len(supporting_files):
                return (result.matched_index, supporting_files[doc_idx].file_name)

        return (-1, "")

    except Exception as e:
        logger.warning(f"Reference matching failed: {e}")
        return (-1, "")


@register_node(
    "Match references to supporting documents",
    "Match extracted references to user-provided supporting documents using LLM",
)
async def match_supporting_docs_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """
    Match extracted references to supporting documents.

    Uses pre-computed document summaries from document processing workflow
    and LLM-based matching for high accuracy across different citation formats.
    """
    extracted_reference_texts = state.extracted_reference_texts
    summaries = state.supporting_documents_summaries or {}
    supporting_files = state.supporting_files or []

    if not extracted_reference_texts:
        logger.info("No extracted reference texts to match")
        return {"references": []}

    logger.info(
        f"Matching {len(extracted_reference_texts)} references against {len(summaries)} document summaries"
    )

    # Match references in parallel with rate limiting
    if summaries and supporting_files:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_MATCHES)

        async def match_with_limit(ref_text: str) -> tuple[int, str]:
            async with semaphore:
                return await _match_reference(
                    ref_text, summaries, supporting_files, runtime.context
                )

        match_results = await asyncio.gather(
            *[match_with_limit(t) for t in extracted_reference_texts]
        )
    else:
        match_results = [(-1, "") for _ in extracted_reference_texts]

    references: List[BibliographyItem] = []
    matched_count = 0

    for ref_text, (match_index, match_name) in zip(
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
            )
        )

    logger.info(f"Matched {matched_count}/{len(references)} references to documents")

    return {"references": references}
