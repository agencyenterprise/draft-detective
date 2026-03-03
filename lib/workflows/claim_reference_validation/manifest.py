from typing import List, Optional, Type, cast

from langgraph.graph import StateGraph

from lib.agents.claim_verifier import ClaimEvidenceSource
from lib.services.file import FileDocument
from lib.workflows.claim_reference_validation.graph import (
    build_claim_reference_validation_graph,
)
from lib.workflows.claim_reference_validation.state import (
    ClaimReferenceValidationState,
    ClaimReferenceValidationWorkflowConfig,
)
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type


def _get_file_document_by_file_id(
    supporting_files: Optional[List[FileDocument]],
    file_id: str,
) -> Optional[FileDocument]:
    """Look up file document by file ID from supporting files."""
    if not supporting_files:
        return None
    for file in supporting_files:
        if file.file_id == file_id:
            return file
    return None


class ClaimReferenceValidationManifest(
    WorkflowManifest[
        ClaimReferenceValidationState, ClaimReferenceValidationWorkflowConfig
    ]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    name = "Claim Reference Validation"
    description = """Validate claims by checking them against supporting documents using RAG (Retrieval-Augmented Generation). Retrieves relevant passages from supporting documents and verifies whether claims are supported, partially supported, unsupported, or unverifiable."""
    needs_web_search = False
    order = 3
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

    def _format_evidence_source(
        self,
        source: ClaimEvidenceSource,
        supporting_files: Optional[List[FileDocument]],
    ) -> str:
        """Format an evidence source with a download link if file ID is available."""
        file = _get_file_document_by_file_id(supporting_files, source.file_id)
        if file:
            file_link = f"[{file.file_name}](/api/files/download/{file.file_id})"
        else:
            file_link = f"File not found (file_id: {source.file_id})"

        if not source.quote and not source.location:
            return f"- {file_link}"

        if not source.quote:
            return f"- {file_link} - {source.location}"

        if not source.location:
            return f"- {file_link}\n\n\t> *{source.quote}*"

        return f"- {file_link} - {source.location}\n\n\t> *{source.quote}*"

    def convert_state_to_issues(
        self,
        state: ClaimReferenceValidationState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert ClaimReferenceValidationState to issues."""
        from lib.agents.claim_verifier import EvidenceAlignmentLevel

        issues: List[DocumentIssue] = []

        # Get supporting files from document processing state for file download links
        doc_processing_state = get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING, other_states
        )
        supporting_files = (
            cast(DocumentProcessingState, doc_processing_state).supporting_files
            if doc_processing_state
            else None
        )

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
            EvidenceAlignmentLevel.SUPPORTED: (
                "Supported Claim",
                SeverityEnum.NONE,
            ),
        }

        # Claim Verification: Unsupported, partially supported, and unverifiable claims
        for substantiation in state.substantiations:
            if substantiation.evidence_alignment not in issue_config:
                continue

            title, severity = issue_config[substantiation.evidence_alignment]

            sources_text = (
                "\n".join(
                    [
                        self._format_evidence_source(source, supporting_files)
                        for source in substantiation.evidence_sources
                    ]
                )
                if substantiation.evidence_sources
                else "*No sources found*"
            )
            long_description = (
                f"**Key sentence:** \n\n> {substantiation.key_sentence}\n\n"
                f"**Evidence Alignment:** {substantiation.evidence_alignment}\n\n"
                f"**Feedback to resolve:** {substantiation.feedback}\n\n"
                f"### Checked sources\n\n{sources_text}\n\n"
                f"### Citation-to-file mapping\n\n{substantiation.citation_to_file_mapping or "No citation-to-file mapping provided"}"
            )

            issues.append(
                DocumentIssue(
                    title=title,
                    description=substantiation.rationale,
                    severity=severity,
                    type=self.type,
                    chunk_indices=[substantiation.chunk_index],
                    long_description=long_description,
                )
            )

        # Claim Categorization: Claims needing external verification without citations
        # for chunk in chunks:
        #     if not chunk.claim_categories:
        #         continue

        #     # Check if chunk has citations
        #     has_citations = (
        #         chunk.citations
        #         and chunk.citations.citations
        #         and len(chunk.citations.citations) > 0
        #     )

        #     for category in chunk.claim_categories:
        #         claim_verification = next(
        #             (
        #                 s
        #                 for s in state.substantiations
        #                 if chunk.chunk_index == s.chunk_index
        #                 and s.claim_index == category.claim_index
        #             ),
        #             None,
        #         )

        #         if (
        #             category.needs_external_verification
        #             and not has_citations
        #             and (
        #                 claim_verification is None
        #                 or claim_verification.evidence_alignment
        #                 != EvidenceAlignmentLevel.SUPPORTED
        #             )
        #         ):
        #             issue = DocumentIssue(
        #                 title="Unsupported claim",
        #                 description=f'Claim requires external verification but no citations/references were found or used: "{category.claim}"',
        #                 severity=SeverityEnum.MEDIUM,
        #                 type=self.type,
        #                 chunk_index=category.chunk_index,
        #                 long_description=f"**Rationale:** {category.rationale}",
        #             )
        #             issues.append(issue)

        return issues
