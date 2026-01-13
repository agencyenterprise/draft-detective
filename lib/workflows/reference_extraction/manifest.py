"""Manifest for reference extraction workflow."""

from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import find_chunk_index_by_text
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_extraction.graph import build_reference_extraction_graph
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import (
    get_main_file_id,
    get_state_by_type_or_raise,
    get_supporting_file_ids,
)


class ReferenceExtractionManifest(
    WorkflowManifest[ReferenceExtractionState, ReferenceExtractionConfig]
):
    """Manifest for reference extraction workflow."""

    type = WorkflowRunType.REFERENCE_EXTRACTION
    name = "Reference Extraction"
    description = "Extract bibliographic references from document using section detection and windowed extraction"
    needs_web_search = False
    is_internal = True  # Runs as dependency, not user-triggered from workflow list
    can_be_triggered_by_user = True  # Can be used as standalone tool
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[ReferenceExtractionState]:
        """Get the type of the workflow state."""
        return ReferenceExtractionState

    def get_config_type(self) -> Type[ReferenceExtractionConfig]:
        """Get the type of the workflow config."""
        return ReferenceExtractionConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_extraction_graph()

    async def create_initial_state(
        self,
        config: ReferenceExtractionConfig,
        existing_states: List[WorkflowState],
    ) -> ReferenceExtractionState:
        """
        Create initial state from DOCUMENT_PROCESSING dependency.

        Gets file with markdown from DOCUMENT_PROCESSING workflow.
        """

        return ReferenceExtractionState(
            type=WorkflowRunType.REFERENCE_EXTRACTION,
            config=config,
            file_id=get_main_file_id(existing_states),
            supporting_file_ids=get_supporting_file_ids(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ReferenceExtractionState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert reference extraction state to issues."""
        issues: List[DocumentIssue] = []

        # Get chunks from document processing state to find chunk indices
        doc_processing_state = cast(
            DocumentProcessingState,
            get_state_by_type_or_raise(
                WorkflowRunType.DOCUMENT_PROCESSING, other_states
            ),
        )

        # References without matching supporting documents
        for reference in state.references:
            if not reference.has_associated_supporting_document:
                issue = DocumentIssue(
                    title="Missing supporting document for reference",
                    description=f'Reference does not have an associated supporting document: "{reference.text}"',
                    severity=SeverityEnum.LOW,
                    chunk_index=find_chunk_index_by_text(
                        doc_processing_state.chunks, reference.text
                    ),
                )
                issues.append(issue)

        return issues
