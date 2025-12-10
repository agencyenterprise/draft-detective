import logging

from langgraph.runtime import Runtime

from lib.agents.evidence_weighter import (
    EvidenceWeighterAgent,
    EvidenceWeighterResponseWithClaimIndex,
)
from lib.agents.live_literature_review import LiveLiteratureReviewAgent
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
    SubstantiationWorkflowConfig,
)
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Live Reports: generate analysis",
    "Generate a live reports analysis from the document and by searching the web",
)
async def generate_live_reports_analysis(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    if not state.config.run_live_reports:
        logger.info(
            f"live_reports_analysis ({state.config.session_id}): skipping live reports (run_live_reports is False)"
        )
        return {}

    if not state.config.document_publication_date:
        logger.warning(
            f"live_reports_analysis ({state.config.session_id}): No document publication date provided, skipping live reports"
        )
        return {}

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
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    live_literature_review_agent: LiveLiteratureReviewAgent,
    evidence_weighter_agent: EvidenceWeighterAgent,
) -> DocumentChunk:
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

        try:
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

        except Exception as e:
            logger.error(
                f"Error processing live reports for chunk {chunk.chunk_index}, claim {claim_index}: {e}",
                exc_info=True,
            )
            # Continue processing other claims even if one fails
            continue

    return chunk.model_copy(
        update={
            "live_reports_analysis": live_reports_analysis_results,
        }
    )


# %%
if __name__ == "__main__":
    import argparse
    import asyncio
    import json
    from datetime import datetime

    import nest_asyncio
    from rich.console import Console
    from rich.panel import Panel

    from lib.agents.citation_detector import Citation, CitationResponse, CitationType
    from lib.agents.claim_extractor import Claim, ClaimResponse
    from lib.agents.reference_extractor import BibliographyItem
    from lib.services.file import FileDocument

    nest_asyncio.apply()

    console = Console()

    async def test_live_reports():
        # Create a test document chunk
        test_chunk = DocumentChunk(
            chunk_index=0,
            paragraph_index=0,
            content="Bitcoin is a decentralized digital currency.",
            claims=ClaimResponse(
                claims=[
                    Claim(
                        text="Bitcoin is a decentralized digital currency.",
                        claim="Bitcoin is a decentralized digital currency.",
                        rationale="Test rationale",
                    )
                ],
                rationale="Extracted a simple claim for testing",
            ),
            citations=CitationResponse(
                citations=[
                    Citation(
                        text="(Nakamoto, 2008)",
                        type="bibliography",
                        format="(Author, Year)",
                        needs_bibliography=True,
                        associated_bibliography="Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.",
                        index_of_associated_bibliography=1,
                        rationale="Example citation",
                    )
                ],
                rationale="Detected one bibliography-style citation for testing",
            ),
        )

        # Create test state
        test_state = ClaimSubstantiatorState(
            file=FileDocument(
                file_name="test.md",
                file_path="/tmp/test.md",
                file_type="text/markdown",
                markdown="# Test Document\n\nBitcoin is a decentralized digital currency.",
                markdown_token_count=100,
            ),
            config=SubstantiationWorkflowConfig(
                run_live_reports=True,
                session_id="test-session",
                domain="cryptocurrency",
                target_audience="technical",
                document_publication_date=datetime(2023, 1, 1).date(),
                agents_to_run=["live_reports"],
            ),
            references=[
                BibliographyItem(
                    text="Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System.",
                    has_associated_supporting_document=False,
                    index_of_associated_supporting_document=-1,
                    name_of_associated_supporting_document="",
                )
            ],
            chunks=[test_chunk],
        )

        console.print("\n[bold cyan]Running Live Reports Analysis Test[/bold cyan]")
        console.print("\n[yellow]Input State:[/yellow]")
        console.print(Panel(test_state.model_dump_json(indent=2), title="Test State"))

        console.print("\n[yellow]Input Chunk:[/yellow]")
        console.print(Panel(test_chunk.model_dump_json(indent=2), title="Test Chunk"))

        try:
            # Test the live reports analysis
            result = await _analyze_chunk_live_reports(test_state, test_chunk)

            console.print("\n[green]Analysis Results:[/green]")
            console.print(
                Panel(
                    json.dumps(result.live_reports_analysis, indent=2, default=str),
                    title="Live Reports Analysis Results",
                )
            )

        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red]")
            console.print(Panel(str(e), title="Error", style="red"))

    parser = argparse.ArgumentParser(description="Test Live Reports Analysis")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args, _ = parser.parse_known_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    console.print("\n[bold]Starting Live Reports Analysis Test[/bold]")
    console.print("[dim]Run with --debug flag for detailed logging[/dim]")

    asyncio.run(test_live_reports())

# %%
