import logging
from typing import List, Optional, Tuple

from langgraph.runtime import Runtime

from lib.agents.citation_suggester import (
    CitationSuggesterAgent,
    CitationSuggestionResultWithClaimIndex,
)
from lib.agents.formatting_utils import (
    format_bibliography_prompt_section,
    format_cited_references,
)
from lib.models.bibliography_item import BibliographyItem
from lib.run_utils import convert_exceptions_to_workflow_errors, run_tasks
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.workflows.citation_suggester.state import CitationSuggesterState
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.document_processing.state import FileSummary

logger = logging.getLogger(__name__)


@register_node(
    "Suggest citations",
    "Suggest citations for the claims",
)
async def suggest_citations(
    state: CitationSuggesterState, runtime: Runtime[ContextSchema]
):
    citation_suggester_agent = CitationSuggesterAgent(runtime.context)
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    chunks = await file_artifacts_service.get_chunks()
    file = await file_artifacts_service.get_main_file()
    references = await file_artifacts_service.get_references()
    supporting_files = await file_artifacts_service.get_supporting_files()
    summaries = [
        await file_artifacts_service.get_file_summary(f.file_id)
        for f in supporting_files
    ] + [await file_artifacts_service.get_file_summary(file.file_id)]

    tasks = [
        _suggest_chunk_citations(
            state,
            chunk,
            citation_suggester_agent,
            file_artifacts_service,
            file,
            references,
            supporting_files,
            summaries,
            chunks,
        )
        for chunk in chunks
    ]

    results: Tuple[
        List[List[CitationSuggestionResultWithClaimIndex] | None],
        List[Exception | None],
    ] = await run_tasks(tasks, desc="Suggesting chunk citations")

    citation_suggestions_list, exceptions = results
    errors = convert_exceptions_to_workflow_errors("suggest_citations", exceptions)

    citation_suggestions: List[CitationSuggestionResultWithClaimIndex] = []
    for result_item in citation_suggestions_list:
        if result_item is not None:
            citation_suggestions.extend(result_item)

    return {"citation_suggestions": citation_suggestions, "errors": errors}


async def _suggest_chunk_citations(
    state: CitationSuggesterState,
    chunk: AnalyzedChunk,
    citation_suggester_agent: CitationSuggesterAgent,
    file_artifacts_service: FileArtifactsServiceType,
    file: FileDocument,
    references: List[BibliographyItem],
    supporting_files: List[FileDocument],
    summaries: List[FileSummary],
    chunks: List[AnalyzedChunk],
) -> List[CitationSuggestionResultWithClaimIndex]:
    # Skip if chunk has no claims
    if chunk.claims is None or not chunk.claims.claims:
        logger.debug(
            "Skipping citation suggestions for chunk %s: no claims detected",
            chunk.chunk_index,
        )
        return []

    citation_suggestions = []
    for claim_index, claim in enumerate(chunk.claims.claims):
        category = next(
            (
                result
                for result in chunk.claim_categories
                if result.claim_index == claim_index
            ),
            None,
        )
        if category and not category.needs_external_verification:
            continue

        cited_references = format_cited_references(
            references,
            supporting_files,
            chunk.citations,
            truncate_at_character_count=1000,  # Include only a little bit of the text of the references
        )

        result = await citation_suggester_agent.ainvoke(
            {
                "full_document": file.markdown,
                "bibliography": format_bibliography_prompt_section(
                    references,
                    supporting_files,
                    summaries,
                ),
                "paragraph": file_artifacts_service.get_paragraph_text(
                    chunks, chunk.paragraph_index
                ),
                "chunk": chunk.content,
                "claim": claim.claim,
                "cited_references": cited_references,
                "literature_review_report": state.literature_review,
            }
        )
        citation_suggestions.append(
            CitationSuggestionResultWithClaimIndex(
                chunk_index=chunk.chunk_index,
                claim_index=claim_index,
                **result.model_dump(),
            )
        )

    return citation_suggestions
