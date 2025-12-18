import logging

from langgraph.runtime import Runtime

from lib.agents.evidence_weighter import (
    EvidenceWeighterAgent,
    EvidenceWeighterResponseWithClaimIndex,
)
from lib.agents.live_literature_review import LiveLiteratureReviewAgent
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import AnalyzedChunk
from lib.workflows.decorators import register_node
from lib.workflows.live_reports.state import LiveReportsState

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

    return await iterate_chunks(
        state,
        _analyze_chunk_live_reports,
        "Analyzing chunk live reports",
        live_literature_review_agent=live_literature_review_agent,
        evidence_weighter_agent=evidence_weighter_agent,
    )


async def _analyze_chunk_live_reports(
    state: LiveReportsState,
    chunk: AnalyzedChunk,
    live_literature_review_agent: LiveLiteratureReviewAgent,
    evidence_weighter_agent: EvidenceWeighterAgent,
) -> AnalyzedChunk:
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping live reports analysis for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return chunk

    live_reports_analysis_results = []

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

    return chunk.model_copy(
        update={
            "live_reports_analysis": live_reports_analysis_results,
        }
    )
