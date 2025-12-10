# %%
import logging

from langgraph.runtime import Runtime

from lib.agents.claim_categorizer import (
    ClaimCategorizationResponseWithClaimIndex,
    ClaimCategorizerAgent,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.workflows.chunk_iterator import iterate_chunks
from lib.workflows.context import ContextSchema
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
)
from lib.workflows.decorators import (
    handle_chunk_errors,
    register_node,
)

logger = logging.getLogger(__name__)


@register_node(
    "Categorize claims",
    "Categorize claims into categories",
)
async def categorize_claims(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    claim_categorizer_agent = ClaimCategorizerAgent(runtime.context)

    return await iterate_chunks(
        state,
        _categorize_chunk_claims,
        "Categorizing claims",
        claim_categorizer_agent=claim_categorizer_agent,
    )


@handle_chunk_errors("Claim categorization")
async def _categorize_chunk_claims(
    state: ClaimSubstantiatorState,
    chunk: DocumentChunk,
    claim_categorizer_agent: ClaimCategorizerAgent,
) -> DocumentChunk:
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping claim categorization for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return chunk

    categorization_results = []
    for claim_index, claim in enumerate(chunk.claims.claims):
        result = await claim_categorizer_agent.ainvoke(
            {
                "document_summary": (
                    state.main_document_summary.summary
                    if state.main_document_summary
                    else ""
                ),
                "paragraph": state.get_paragraph(chunk.paragraph_index),
                "chunk": chunk.content,
                "claim": claim.claim,
                "domain_context": format_domain_context(state.config.domain),
                "audience_context": format_audience_context(
                    state.config.target_audience
                ),
            }
        )
        categorization_results.append(
            ClaimCategorizationResponseWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    return chunk.model_copy(update={"claim_categories": categorization_results})


if __name__ == "__main__":
    import argparse
    import asyncio
    import json
    from datetime import datetime

    import nest_asyncio
    from rich.console import Console
    from rich.panel import Panel

    from lib.agents.claim_extractor import Claim, ClaimResponse
    from lib.services.file import FileDocument
    from lib.workflows.claim_substantiation.state import SubstantiationWorkflowConfig

    nest_asyncio.apply()

    console = Console()

    async def test_claim_categorization():
        # Create a test document chunk
        test_chunk = DocumentChunk(
            chunk_index=0,
            paragraph_index=0,
            content="Machine learning models have shown superior performance on image classification tasks compared to traditional computer vision approaches.",
            claims=ClaimResponse(
                claims=[
                    Claim(
                        text="Machine learning models have shown superior performance on image classification tasks",
                        claim="Machine learning models outperform traditional computer vision approaches on image classification",
                        rationale="The text directly states the comparative performance advantage",
                    )
                ],
                rationale="Extracted a comparative claim about ML performance",
            ),
        )

        # Create test state
        test_state = ClaimSubstantiatorState(
            file=FileDocument(
                file_name="test.md",
                file_path="/tmp/test.md",
                file_type="text/markdown",
                markdown="# Test Document\n\nMachine learning models have shown superior performance on image classification tasks compared to traditional computer vision approaches.",
            ),
            config=SubstantiationWorkflowConfig(
                session_id="test-session",
                domain="machine learning",
                target_audience="technical",
            ),
            chunks=[test_chunk],
        )

        console.print("\n[bold cyan]Running Claim Categorization Test[/bold cyan]")
        console.print("\n[yellow]Input Chunk:[/yellow]")
        console.print(Panel(test_chunk.model_dump_json(indent=2), title="Test Chunk"))

        try:
            # Create agent with context for testing
            from lib.config.env import config

            context = ContextSchema(
                openai_api_key=config.OPENAI_API_KEY, vector_store=None
            )
            claim_categorizer_agent = ClaimCategorizerAgent(context)

            # Test the claim categorization
            result = await _categorize_chunk_claims(
                test_state, test_chunk, claim_categorizer_agent
            )

            console.print("\n[green]Categorization Results:[/green]")
            if result.claim_categories:
                for cat_result in result.claim_categories:
                    console.print(
                        Panel(
                            json.dumps(
                                cat_result.model_dump(),
                                indent=2,
                                default=str,
                                ensure_ascii=False,
                            ),
                            title=f"Claim {cat_result.claim_index} - {cat_result.claim_category.value}",
                        )
                    )
            else:
                console.print("[yellow]No categorization results[/yellow]")

        except Exception as e:
            console.print(f"\n[red]Error during categorization:[/red]")
            console.print(Panel(str(e), title="Error", style="red"))
            import traceback

            traceback.print_exc()

    parser = argparse.ArgumentParser(description="Test Claim Categorization")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args, _ = parser.parse_known_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    console.print("\n[bold]Starting Claim Categorization Test[/bold]")
    console.print("[dim]Run with --debug flag for detailed logging[/dim]")

    asyncio.run(test_claim_categorization())
