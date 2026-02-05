from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import build_analyzed_chunks, find_chunk_by_index
from lib.workflows.inference_validation.graph import build_inference_validation_graph
from lib.workflows.inference_validation.state import (
    InferenceValidationState,
    InferenceValidationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id


class InferenceValidationManifest(
    WorkflowManifest[InferenceValidationState, InferenceValidationWorkflowConfig]
):
    type = WorkflowRunType.INFERENCE_VALIDATION
    name = "Inference Validation"
    description = """Validate inferential claims (claims classified as "interpretation") using the Toulmin model of argumentation. Analyzes the logical structure of inferences by examining claims, data/grounds, warrants, qualifiers, rebuttals, and backing. Identifies invalid inferences where the reasoning fails to meet Toulmin argumentation standards and flags them as issues."""
    needs_web_search = False
    order = 1
    required_dependencies = [
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
    ]

    def get_state_type(self) -> Type[InferenceValidationState]:
        """Get the type of the workflow state."""
        return InferenceValidationState

    def get_config_type(self) -> Type[InferenceValidationWorkflowConfig]:
        """Get the type of the workflow config."""
        return InferenceValidationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_inference_validation_graph()

    async def create_initial_state(
        self,
        config: InferenceValidationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> InferenceValidationState:
        """Create and return the initial state of the workflow."""

        return InferenceValidationState(
            type=WorkflowRunType.INFERENCE_VALIDATION,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self, state: InferenceValidationState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert InferenceValidationState to issues."""
        issues: List[DocumentIssue] = []
        chunks = build_analyzed_chunks(other_states)

        for validation in state.inference_validations:
            if not validation.valid:
                chunk = find_chunk_by_index(chunks, validation.chunk_index)
                issues.append(
                    DocumentIssue(
                        title="Invalid Inference",
                        description=validation.rationale,
                        severity=SeverityEnum.MEDIUM,
                        type=self.type,
                        chunk_index=validation.chunk_index,
                        claim_index=validation.claim_index,
                    )
                )

        return issues
