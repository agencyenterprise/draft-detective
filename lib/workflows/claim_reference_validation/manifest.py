from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import (
    build_analyzed_chunks,
    find_chunk_by_index,
    find_claim_category,
)
from lib.workflows.claim_reference_validation.graph import (
    build_claim_reference_validation_graph,
)
from lib.workflows.claim_reference_validation.state import (
    ClaimReferenceValidationState,
    ClaimReferenceValidationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState


class ClaimReferenceValidationManifest(
    WorkflowManifest[
        ClaimReferenceValidationState, ClaimReferenceValidationWorkflowConfig
    ]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    name = "Claim Reference Validation"
    description = """Validate claims by checking them against supporting documents using RAG (Retrieval-Augmented Generation). Retrieves relevant passages from supporting documents and verifies whether claims are supported, partially supported, unsupported, or unverifiable."""
    needs_web_search = False
    order = 2
    required_dependencies = [
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.CITATION_DETECTION,
        WorkflowRunType.REFERENCE_FILE_MATCHING,
    ]
    optional_dependencies = [
        WorkflowRunType.HUMAN_APPROVAL,
    ]

    def get_state_type(self) -> Type[ClaimReferenceValidationState]:
        """Get the type of the workflow state."""
        return ClaimReferenceValidationState

    def get_config_type(self) -> Type[ClaimReferenceValidationWorkflowConfig]:
        """Get the type of the workflow config."""
        return ClaimReferenceValidationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_claim_reference_validation_graph()

    async def create_initial_state(
        self,
        config: ClaimReferenceValidationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimReferenceValidationState:
        """Create and return the initial state of the workflow."""

        return ClaimReferenceValidationState(
            type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            config=config,
        )

    def convert_state_to_issues(
        self,
        state: ClaimReferenceValidationState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert ClaimReferenceValidationState to issues."""
        from lib.agents.claim_verifier import EvidenceAlignmentLevel

        issues: List[DocumentIssue] = []
        chunks = build_analyzed_chunks(other_states)

        # Map evidence alignment levels to issue titles and severities
        issue_config = {
            EvidenceAlignmentLevel.UNSUPPORTED: (
                "Unsupported Claim",
                SeverityEnum.HIGH,
            ),
            EvidenceAlignmentLevel.PARTIALLY_SUPPORTED: (
                "Partially Supported Claim",
                SeverityEnum.MEDIUM,
            ),
            EvidenceAlignmentLevel.UNVERIFIABLE: (
                "Unverifiable Claim",
                SeverityEnum.MEDIUM,
            ),
        }

        # Claim Verification: Unsupported, partially supported, and unverifiable claims
        for substantiation in state.substantiations:
            if substantiation.evidence_alignment not in issue_config:
                continue

            title, severity = issue_config[substantiation.evidence_alignment]
            chunk = find_chunk_by_index(chunks, substantiation.chunk_index)

            issues.append(
                DocumentIssue(
                    title=title,
                    description=substantiation.rationale,
                    severity=severity,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=find_claim_category(
                        chunk, substantiation.claim_index
                    ),
                )
            )

        # Claim Categorization: Claims needing external verification without citations
        for chunk in chunks:
            if not chunk.claim_categories:
                continue

            # Check if chunk has citations
            has_citations = (
                chunk.citations
                and chunk.citations.citations
                and len(chunk.citations.citations) > 0
            )

            for category in chunk.claim_categories:
                claim_verification = next(
                    (
                        s
                        for s in state.substantiations
                        if chunk.chunk_index == s.chunk_index
                        and s.claim_index == category.claim_index
                    ),
                    None,
                )

                if (
                    category.needs_external_verification
                    and not has_citations
                    and (
                        claim_verification is None
                        or claim_verification.evidence_alignment
                        != EvidenceAlignmentLevel.SUPPORTED
                    )
                ):
                    issue = DocumentIssue(
                        title="Unsupported claim",
                        description=f"Claim '{category.claim}' requires external verification but no citations were found.",
                        severity=SeverityEnum.MEDIUM,
                        chunk_index=category.chunk_index,
                        claim_index=category.claim_index,
                        claim_category=category.claim_category,
                    )
                    issues.append(issue)

        return issues
