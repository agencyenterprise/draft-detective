"""Manifest for Claim Reference Validation V2 workflow."""

from typing import List, Optional, Type, cast

from langgraph.graph import StateGraph

from lib.agents.citation_validator import TruthfulnessLabel
from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.services.file import FileDocument
from lib.workflows.claim_reference_validation_v2.graph import (
    build_claim_reference_validation_v2_graph,
)
from lib.workflows.claim_reference_validation_v2.state import (
    CitationIssueItem,
    ClaimReferenceValidationV2Config,
    ClaimReferenceValidationV2State,
    SectionVerificationStatus,
)
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import (
    DocumentIssue,
    SeverityEnum,
    WorkflowGate,
    WorkflowRunType,
)
from lib.workflows.util import get_state_by_type
from lib.workflows.workflow_types import WorkflowState

_ISSUE_CONFIG: dict[EvidenceAlignmentLevel, tuple[str, SeverityEnum]] = {
    EvidenceAlignmentLevel.SUPPORTED: ("Supported Citation", SeverityEnum.NONE),
    EvidenceAlignmentLevel.PARTIALLY_SUPPORTED: (
        "Partially Supported Citation",
        SeverityEnum.MEDIUM,
    ),
    EvidenceAlignmentLevel.UNSUPPORTED: (
        "Unsupported Citation",
        SeverityEnum.HIGH,
    ),
    EvidenceAlignmentLevel.UNVERIFIABLE: (
        "Unverifiable Citation",
        SeverityEnum.MEDIUM,
    ),
}

# Maps the legacy 6-category `TruthfulnessLabel` onto the current
# `EvidenceAlignmentLevel` taxonomy so that workflow state persisted before the
# migration back to `EvidenceAlignmentLevel` still renders correctly.
_LEGACY_LABEL_TO_ALIGNMENT: dict[TruthfulnessLabel, EvidenceAlignmentLevel] = {
    TruthfulnessLabel.TRUE_EXPLICIT: EvidenceAlignmentLevel.SUPPORTED,
    TruthfulnessLabel.TRUE_INFERRED: EvidenceAlignmentLevel.SUPPORTED,
    TruthfulnessLabel.PARTIALLY_TRUE: EvidenceAlignmentLevel.PARTIALLY_SUPPORTED,
    TruthfulnessLabel.FALSE_CONTRADICTED: EvidenceAlignmentLevel.UNSUPPORTED,
    TruthfulnessLabel.FALSE_NOT_IN_TEXT: EvidenceAlignmentLevel.UNSUPPORTED,
    TruthfulnessLabel.UNVERIFIABLE: EvidenceAlignmentLevel.UNVERIFIABLE,
}


def _get_file_by_id(
    supporting_files: Optional[List[FileDocument]], file_id: str
) -> Optional[FileDocument]:
    if not supporting_files:
        return None
    return next((f for f in supporting_files if f.file_id == file_id), None)


def _format_evidence_source(
    source,
    supporting_files: Optional[List[FileDocument]],
) -> str:
    file = _get_file_by_id(supporting_files, source.file_id)
    label = file.file_name if file else "View file"
    file_link = f"[{label}](/api/files/download/{source.file_id})"

    if not source.quote and not source.location:
        return f"- {file_link}"
    if not source.quote:
        return f"- {file_link} - {source.location}"
    if not source.location:
        return f"- {file_link}\n\n\t> *{source.quote}*"
    return f"- {file_link} - {source.location}\n\n\t> *{source.quote}*"


def _resolve_alignment(item: CitationIssueItem) -> Optional[EvidenceAlignmentLevel]:
    if item.evidence_alignment is not None:
        return item.evidence_alignment
    if item.truthfulness_label is not None:
        return _LEGACY_LABEL_TO_ALIGNMENT.get(item.truthfulness_label)
    return None


def _build_issue(
    item: CitationIssueItem,
    supporting_files: Optional[List[FileDocument]],
    workflow_type: WorkflowRunType,
) -> Optional[DocumentIssue]:
    alignment = _resolve_alignment(item)
    if alignment is None or alignment not in _ISSUE_CONFIG:
        return None

    title, severity = _ISSUE_CONFIG[alignment]

    sources_text = (
        "\n".join(
            _format_evidence_source(source, supporting_files)
            for source in item.evidence_sources
        )
        if item.evidence_sources
        else "*No sources found*"
    )

    long_description = (
        f"**Cited text:**\n\n> {item.quoted_text}\n\n"
        f"**Evidence alignment:** {alignment.value}\n\n"
        f"### Checked sources\n\n{sources_text}\n\n"
        f"### Citation-to-file mapping\n\n"
        f"{item.citation_to_file_mapping or 'No citation-to-file mapping provided'}"
    )

    return DocumentIssue(
        title=title,
        description=item.rationale,
        severity=severity,
        type=workflow_type,
        start_line=item.line_start,
        end_line=item.line_end,
        long_description=long_description,
        suggested_action=item.feedback or None,
    )


class ClaimReferenceValidationV2Manifest(
    WorkflowManifest[ClaimReferenceValidationV2State, ClaimReferenceValidationV2Config]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    name = "Claim Reference Validation"
    description = (
        "Checks every citation in your document against its referenced source and "
        "flags claims that aren't supported, are only partially supported, or can't "
        "be verified."
    )
    needs_web_search = False
    is_experimental = False
    required_dependencies = [
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_FILE_MATCHING,
    ]
    # The user reviews the reference-to-file matching (and uploads or fetches
    # missing sources) before this reads the sources.
    gates = [WorkflowGate.REFERENCE_REVIEW]
    optional_dependencies = [
        WorkflowRunType.REFERENCE_DOWNLOADER,
    ]

    def get_state_type(self) -> Type[ClaimReferenceValidationV2State]:
        return ClaimReferenceValidationV2State

    def get_config_type(self) -> Type[ClaimReferenceValidationV2Config]:
        return ClaimReferenceValidationV2Config

    def build_graph(self) -> StateGraph:
        return build_claim_reference_validation_v2_graph()

    async def on_cancel(
        self, state: ClaimReferenceValidationV2State
    ) -> ClaimReferenceValidationV2State:
        updated = [
            (
                item.model_copy(update={"status": SectionVerificationStatus.CANCELLED})
                if item.status == SectionVerificationStatus.PENDING
                else item
            )
            for item in state.section_verifications
        ]
        return state.model_copy(update={"section_verifications": updated})

    async def create_initial_state(
        self,
        config: ClaimReferenceValidationV2Config,
        existing_states: List[WorkflowState],
        revision: int,
        prior_self_state: ClaimReferenceValidationV2State | None = None,
    ) -> ClaimReferenceValidationV2State:
        return ClaimReferenceValidationV2State(
            type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            config=config,
        )

    def convert_state_to_issues(
        self,
        state: ClaimReferenceValidationV2State,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        doc_processing_state = get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING, other_states
        )
        supporting_files = (
            cast(DocumentProcessingState, doc_processing_state).supporting_files
            if doc_processing_state
            else None
        )

        issues = []
        for item in state.citation_issues:
            issue = _build_issue(item, supporting_files, self.type)
            if issue:
                issues.append(issue)

        return issues
