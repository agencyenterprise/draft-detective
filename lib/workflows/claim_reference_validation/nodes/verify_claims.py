import logging
from collections import defaultdict
from typing import List, Optional

from langgraph.runtime import Runtime
from langgraph.types import Send

from lib.agents.citation_detector import Citation
from lib.agents.claim_verifier import (
    ClaimSubstantiationResultWithClaimIndex,
    ClaimVerifierAgent,
    ParagraphVerificationResult,
)
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.models.bibliography_item import (
    BibliographyItem,
    get_associated_supporting_file,
)
from lib.services.file import FileDocument
from lib.workflows.chunk_utils import AnalyzedChunk
from lib.workflows.claim_reference_validation.state import (
    ClaimReferenceValidationState,
    ParagraphVerificationItem,
    ParagraphVerificationStatus,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


def is_bibliographic_citation(citation: Citation) -> bool:
    """Check if a citation is a bibliographic citation."""
    return citation.needs_bibliography


def get_all_paragraph_citations(
    chunks: List[AnalyzedChunk], paragraph_index: int
) -> List[Citation]:
    """Get all bibliographic citations from a paragraph by its index."""
    all_citations: List[Citation] = []
    for chunk in chunks:
        if chunk.paragraph_index != paragraph_index:
            continue
        if not chunk.citations or not chunk.citations.citations:
            continue
        all_citations.extend(
            c for c in chunk.citations.citations if is_bibliographic_citation(c)
        )
    return all_citations


def _build_citation_file_mapping(
    citations: List[Citation],
    references: List[BibliographyItem],
    supporting_files: List[FileDocument],
) -> str:
    """Build a formatted citation-to-file mapping string for the agent prompt.

    Resolves each citation -> bibliography item -> supporting file and returns
    a formatted string the agent can use to identify which file_id to search.
    """
    seen_file_ids: set[str] = set()
    lines: list[str] = []

    for citation in citations:
        bib_index = citation.index_of_associated_bibliography
        if bib_index < 1 or bib_index > len(references):
            continue

        bib_item = references[bib_index - 1]
        supporting_file = get_associated_supporting_file(bib_item, supporting_files)
        if not supporting_file:
            continue
        if supporting_file.file_id in seen_file_ids:
            continue

        seen_file_ids.add(supporting_file.file_id)
        lines.append(
            f'- Citation: "{citation.text}" → '
            f'Bibliography: "{bib_item.text}" → '
            f'File: "{supporting_file.file_name}" (file_id: {supporting_file.file_id})'
        )

    if not lines:
        return "No supporting files are mapped to citations in this paragraph."

    return "\n".join(lines)


def _collect_paragraph_claims(
    paragraph_chunks: List[AnalyzedChunk],
) -> List[dict]:
    """Collect all claims from a paragraph's chunks that need verification.

    Returns a list of dicts with claim metadata:
        {chunk_index, claim_index, claim_text}
    """
    claims: list[dict] = []
    for chunk in paragraph_chunks:
        if not chunk.claims or not chunk.claims.claims:
            continue
        for claim_index, claim in enumerate(chunk.claims.claims):
            # Check claim categories to see if external verification is needed
            claim_category = next(
                (c for c in chunk.claim_categories if c.claim_index == claim_index),
                None,
            )
            # If categorization didn't happen, assume all claims need verification
            if claim_category and not claim_category.needs_external_verification:
                continue

            claims.append(
                {
                    "chunk_index": chunk.chunk_index,
                    "claim_index": claim_index,
                    "claim_text": claim.claim,
                }
            )
    return claims


def _format_claims_list(claims: List[dict]) -> str:
    """Format claims as a numbered list for the agent prompt."""
    lines = []
    for i, claim_info in enumerate(claims, start=1):
        lines.append(f"{i}. {claim_info['claim_text']}")
    return "\n".join(lines)


def _map_results_to_substantiations(
    verification_result: ParagraphVerificationResult,
    claims: List[dict],
) -> List[ClaimSubstantiationResultWithClaimIndex]:
    """Map agent paragraph-level results back to per-claim substantiations."""
    substantiations: list[ClaimSubstantiationResultWithClaimIndex] = []

    for item in verification_result.claim_results:
        # claim_number is 1-indexed, matching the numbered list
        idx = item.claim_number - 1
        if idx < 0 or idx >= len(claims):
            logger.warning(
                f"Agent returned claim_number {item.claim_number} which is out of range "
                f"(expected 1-{len(claims)}), skipping"
            )
            continue

        claim_info = claims[idx]
        substantiations.append(
            ClaimSubstantiationResultWithClaimIndex(
                chunk_index=claim_info["chunk_index"],
                claim_index=claim_info["claim_index"],
                **item.model_dump(),
            )
        )

    return substantiations


def _get_paragraphs_with_citations(
    target_chunks: List[AnalyzedChunk],
) -> dict[int, list[AnalyzedChunk]]:
    """Group chunks by paragraph and filter to those with bibliographic citations."""
    paragraphs: dict[int, list[AnalyzedChunk]] = defaultdict(list)
    for chunk in target_chunks:
        paragraphs[chunk.paragraph_index].append(chunk)

    return {
        p_idx: p_chunks
        for p_idx, p_chunks in paragraphs.items()
        if get_all_paragraph_citations(target_chunks, p_idx)
    }


@register_node(
    "Initialize verifications",
    "Initialize all paragraphs with pending verification status",
)
async def initialize_verifications(
    state: ClaimReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Initialize all paragraphs with PENDING status.

    Fetches chunks, groups by paragraph, filters to those with citations,
    and creates a PENDING tracking item for each eligible paragraph.
    """
    file_artifacts_service = runtime.context.file_artifacts_service
    target_chunks = await file_artifacts_service.get_chunks()

    paragraphs_with_citations = _get_paragraphs_with_citations(target_chunks)

    logger.info(
        f"Found {len(paragraphs_with_citations)} paragraphs with citations "
        f"to verify"
    )

    pending_items = [
        ParagraphVerificationItem(
            paragraph_index=p_idx,
            status=ParagraphVerificationStatus.PENDING,
            num_claims=len(_collect_paragraph_claims(p_chunks)),
        )
        for p_idx, p_chunks in paragraphs_with_citations.items()
    ]

    return {"paragraph_verifications": pending_items}


@register_node(
    "Distribute verifications",
    "Distribute paragraphs to parallel verification operations",
)
async def distribute_verifications(
    state: ClaimReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Fan-out node: creates a Send for each paragraph to verify.

    Dispatches parallel verification operations, passing minimal data
    in each Send payload. Workers fetch shared data from file_artifacts_service.
    """
    return [
        Send(
            "verify_single_paragraph",
            {
                "paragraph_index": item.paragraph_index,
                "domain": state.config.domain,
                "target_audience": state.config.target_audience,
            },
        )
        for item in state.paragraph_verifications
        if item.num_claims > 0
    ]


@register_node(
    "Verify paragraph",
    "Verify claims in a single paragraph",
)
async def verify_single_paragraph(state: dict, runtime: Runtime[ContextSchema]):
    """Process a single paragraph and return verification results.

    Each call handles one paragraph and returns an update that the reducer
    will merge into the state by paragraph_index.
    """
    paragraph_index: int = state["paragraph_index"]
    domain: Optional[str] = state.get("domain")
    target_audience: Optional[str] = state.get("target_audience")

    file_artifacts_service = runtime.context.file_artifacts_service
    claim_verifier_agent = ClaimVerifierAgent(runtime.context)

    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = []
    error: Optional[str] = None
    status = ParagraphVerificationStatus.COMPLETED
    num_claims = 0

    try:
        # Fetch shared data
        target_chunks = await file_artifacts_service.get_chunks()
        supporting_files = await file_artifacts_service.get_supporting_files()
        references = await file_artifacts_service.get_references()

        # Get chunks for this paragraph
        paragraph_chunks = [
            c for c in target_chunks if c.paragraph_index == paragraph_index
        ]

        # Collect claims that need verification
        claims = _collect_paragraph_claims(paragraph_chunks)
        num_claims = len(claims)
        if not claims:
            logger.debug(
                f"Paragraph {paragraph_index} has no claims needing verification"
            )
            return {
                "paragraph_verifications": [
                    ParagraphVerificationItem(
                        paragraph_index=paragraph_index,
                        status=ParagraphVerificationStatus.COMPLETED,
                        num_claims=0,
                    )
                ]
            }

        # Build paragraph text
        paragraph_text = "\n".join(chunk.content for chunk in paragraph_chunks)

        # Build citation-to-file mapping
        paragraph_citations = get_all_paragraph_citations(
            target_chunks, paragraph_index
        )
        citation_file_mapping = _build_citation_file_mapping(
            paragraph_citations, references, supporting_files
        )

        # Build the numbered claims list
        claims_list = _format_claims_list(claims)

        logger.info(
            f"Verifying paragraph {paragraph_index}: {len(claims)} claims, "
            f"{len(paragraph_citations)} citations"
        )

        # Call the agent
        result = await claim_verifier_agent.ainvoke(
            {
                "paragraph": paragraph_text,
                "claims_list": claims_list,
                "citation_file_mapping": citation_file_mapping,
                "domain_context": format_domain_context(domain),
                "audience_context": format_audience_context(target_audience),
            }
        )

        substantiations = _map_results_to_substantiations(result, claims)

    except Exception as e:
        logger.error(f"Error verifying paragraph {paragraph_index}: {e}", exc_info=True)
        status = ParagraphVerificationStatus.ERROR
        error = str(e)

    return {
        "paragraph_verifications": [
            ParagraphVerificationItem(
                paragraph_index=paragraph_index,
                status=status,
                num_claims=num_claims,
                substantiations=substantiations,
                error=error,
            )
        ]
    }


@register_node(
    "Finalize verifications",
    "Finalize claim verification results",
)
async def finalize_verifications(
    state: ClaimReferenceValidationState, runtime: Runtime[ContextSchema]
):
    """Finalize verification results after all parallel verifications complete.

    Flattens paragraph-level substantiations into the top-level list and
    collects errors from failed paragraphs.
    """
    all_substantiations: List[ClaimSubstantiationResultWithClaimIndex] = []
    errors: List[WorkflowError] = []

    for item in state.paragraph_verifications:
        if item.status == ParagraphVerificationStatus.COMPLETED:
            all_substantiations.extend(item.substantiations)
        elif item.status == ParagraphVerificationStatus.ERROR:
            errors.append(
                WorkflowError(
                    task_name="verify_claims",
                    error=item.error or "Unknown error",
                    workflow_run_id=runtime.context.workflow_run_id,
                )
            )

    return {"substantiations": all_substantiations, "errors": errors}
