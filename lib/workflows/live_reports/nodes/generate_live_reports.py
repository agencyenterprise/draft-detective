import logging
from typing import List

from langgraph.runtime import Runtime

from lib.agents.evidence_weighter import (
    EvidenceWeighterAgent,
    EvidenceWeighterResponseWithClaimIndex,
)
from lib.agents.live_literature_review import LiveLiteratureReviewAgent
from lib.run_utils import run_tasks
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.live_reports.state import LiveReportsState
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


@register_node(
    "Live Reports: generate analysis",
    "Generate a live reports analysis from the document and by searching the web",
)
async def generate_live_reports_analysis(
    state: LiveReportsState, runtime: Runtime[ContextSchema]
) -> LiveReportsState:
    live_literature_review_agent = LiveLiteratureReviewAgent(runtime.context)
    evidence_weighter_agent = EvidenceWeighterAgent(runtime.context)

    # Process all chunks
    tasks = [
        _analyze_chunk_live_reports(
            state, chunk, live_literature_review_agent, evidence_weighter_agent
        )
        for chunk in state.chunks
    ]

    results: tuple[
        list[list[EvidenceWeighterResponseWithClaimIndex] | None],
        list[Exception | None],
    ] = await run_tasks(tasks, desc="Analyzing chunk live reports")
    live_reports_analysis_results_raw, exceptions = results

    # Filter out None results
    live_reports_analysis_results: List[EvidenceWeighterResponseWithClaimIndex] = []
    for chunk_results in live_reports_analysis_results_raw:
        if chunk_results is not None:
            live_reports_analysis_results.extend(chunk_results)

    # Collect errors
    errors = []
    for index, exception in enumerate(exceptions):
        if exception is not None:
            chunk_index = state.chunks[index].chunk_index
            errors.append(
                WorkflowError(
                    task_name="generate_live_reports_analysis",
                    error=str(exception),
                    chunk_index=chunk_index,
                )
            )

    return {"live_reports_analysis": live_reports_analysis_results, "errors": errors}


async def _analyze_chunk_live_reports(
    state: LiveReportsState,
    chunk: AnalyzedChunk,
    live_literature_review_agent: LiveLiteratureReviewAgent,
    evidence_weighter_agent: EvidenceWeighterAgent,
) -> List[EvidenceWeighterResponseWithClaimIndex]:
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping live reports analysis for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return []

    live_reports_analysis_results: List[EvidenceWeighterResponseWithClaimIndex] = []

    for claim_index, claim in enumerate(chunk.claims.claims):
        # Skip non-central claims - only analyze central claims for live reports
        # Note: ToulminClaim doesn't have a central field, so we process all Toulmin claims
        if hasattr(claim, "central") and not claim.central:
            logger.debug(
                "Skipping live reports analysis for chunk %s, claim %s: claim is not central",
                chunk.chunk_index,
                claim_index,
            )
            continue

        # Step 1: Find newer literature
        literature_review_result = await live_literature_review_agent.ainvoke(
            {
                "document_summary": (
                    state.main_document_summary.summary
                    if state.main_document_summary
                    else ""
                ),
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "claim": claim.claim,
                "document_publication_date": state.config.document_publication_date.isoformat(),
                "domain_context": state.config.domain or "",
                "audience_context": state.config.target_audience or "",
                "bibliography": state.references,
            }
        )

        # Step 2: Analyze evidence strength and direction and update recommendations
        live_reports_analysis_result = await evidence_weighter_agent.ainvoke(
            {
                "document_summary": (
                    state.main_document_summary.summary
                    if state.main_document_summary
                    else ""
                ),
                "cited_references": (
                    chunk.citations.citations if chunk.citations else []
                ),
                "cited_references_paragraph": [],  # TODO (2025-10-20): Get citations from paragraph
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "domain_context": state.config.domain or "",
                "audience_context": state.config.target_audience or "",
                "newer_references": literature_review_result.newer_references,
                "evidence_summary": literature_review_result.references_summary,
            }
        )

        live_reports_analysis_results.append(
            EvidenceWeighterResponseWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **live_reports_analysis_result.model_dump(),
            )
        )

    return live_reports_analysis_results
