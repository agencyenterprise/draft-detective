from datetime import date
from lib.agents.formatting_utils import (
    format_domain_context,
    format_audience_context,
    format_summary_context,
)
from typing import List

from langgraph.runtime import Runtime

from lib.agents.document_summarizer import DocumentSummary
from lib.agents.evidence_weighter import (
    EvidenceWeighterAgent,
    EvidenceWeighterResponseWithClaimIndex,
)
from lib.agents.formatting_utils import format_bibliography
from lib.agents.live_literature_review import LiveLiteratureReviewAgent
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.services.file_artifacts_service.file_artifacts_service_type import FileArtifactsServiceType
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.live_reports.state import LiveReportsState
from lib.workflows.reference_extraction.state import ExtractedReference


import logging

logger = logging.getLogger(__name__)


@register_node(
    "Live Reports: generate analysis",
    "Generate a live reports analysis from the document and by searching the web",
)
async def generate_live_reports_analysis(
    state: LiveReportsState, runtime: Runtime[ContextSchema]
):
    live_literature_review_agent = LiveLiteratureReviewAgent(runtime.context)
    evidence_weighter_agent = EvidenceWeighterAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    chunks = await file_artifacts_service.get_chunks()
    document_summary = await file_artifacts_service.get_file_summary(state.file_id)
    # Use extracted references (no file matching needed for live reports)
    references = await file_artifacts_service.get_extracted_references()

    # Process all chunks
    tasks = [
        _analyze_chunk_live_reports(
            state,
            chunk,
            chunks,
            document_summary,
            references,
            live_literature_review_agent,
            evidence_weighter_agent,
            file_artifacts_service,
        )
        for chunk in chunks
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
    chunk_indices = [c.chunk_index for c in chunks]
    errors = convert_exceptions_to_workflow_errors(
        "generate_live_reports_analysis",
        exceptions,
        chunk_indices,
        workflow_run_id=runtime.context.workflow_run_id,
    )

    return {"live_reports_analysis": live_reports_analysis_results, "errors": errors}


async def _analyze_chunk_live_reports(
    state: LiveReportsState,
    chunk: AnalyzedChunk,
    chunks: List[AnalyzedChunk],
    document_summary: DocumentSummary,
    references: List[ExtractedReference],
    live_literature_review_agent: LiveLiteratureReviewAgent,
    evidence_weighter_agent: EvidenceWeighterAgent,
    file_artifacts_service: FileArtifactsServiceType,
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
                "summary_context": (
                    format_summary_context(document_summary.summary)
                    if document_summary
                    else ""
                ),
                "paragraph": file_artifacts_service.get_paragraph_text(
                    chunks, chunk.paragraph_index
                ),
                "claim": claim.claim,
                "document_publication_date": (
                    state.config.publication_date
                    if state.config.publication_date
                    else date.today().isoformat()
                ),
                "domain_context": format_domain_context(state.config.domain),
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
                "bibliography": format_bibliography(references),
            }
        )

        # Step 2: Analyze evidence strength and direction and update recommendations
        live_reports_analysis_result = await evidence_weighter_agent.ainvoke(
            {
                "summary_context": (
                    format_summary_context(document_summary.summary)
                    if document_summary
                    else ""
                ),
                "cited_references": (
                    chunk.citations.citations if chunk.citations else []
                ),
                "cited_references_paragraph": [],  # TODO (2025-10-20): Get citations from paragraph
                "paragraph": file_artifacts_service.get_paragraph_text(
                    chunks, chunk.paragraph_index
                ),
                "chunk": chunk.content,
                "claim": claim.claim,
                "domain_context": format_domain_context(state.config.domain),
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
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
