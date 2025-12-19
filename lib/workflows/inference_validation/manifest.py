from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.issue_converter import _find_claim_category
from lib.workflows.claim_substantiation.state import (
    AnalyzedChunk,
    ClaimSubstantiatorState,
)
from lib.workflows.inference_validation.graph import build_inference_validation_graph
from lib.workflows.inference_validation.state import (
    InferenceValidationState,
    InferenceValidationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class InferenceValidationManifest(
    WorkflowManifest[InferenceValidationState, InferenceValidationWorkflowConfig]
):
    type = WorkflowRunType.INFERENCE_VALIDATION
    name = "Inference Validation"
    description = """Validate inferential claims (claims classified as "interpretation") using the Toulmin model of argumentation. Analyzes the logical structure of inferences by examining claims, data/grounds, warrants, qualifiers, rebuttals, and backing. Identifies invalid inferences where the reasoning fails to meet Toulmin argumentation standards and flags them as issues."""
    needs_web_search = False
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

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

        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        # Carry over optional context from the claim workflow if not provided
        if config.domain is None:
            config.domain = claim_state.config.domain
        if config.target_audience is None:
            config.target_audience = claim_state.config.target_audience

        return InferenceValidationState(
            type=WorkflowRunType.INFERENCE_VALIDATION,
            config=config,
            file=claim_state.file,
            chunks=claim_state.chunks,
            main_document_summary=claim_state.main_document_summary,
        )

    def convert_state_to_issues(
        self, state: InferenceValidationState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert InferenceValidationState to issues."""
        issues: List[DocumentIssue] = []

        # Inference Validation: Invalid inferences
        for validation in state.inference_validations:
            if not validation.valid:
                # Find the chunk to get claim category
                chunk: AnalyzedChunk | None = None
                for c in state.chunks:
                    if c.chunk_index == validation.chunk_index:
                        chunk = c
                        break

                issue = DocumentIssue(
                    title="Invalid Inference",
                    description=validation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=validation.chunk_index,
                    claim_index=validation.claim_index,
                    claim_category=(
                        _find_claim_category(chunk, validation.claim_index)
                        if chunk
                        else None
                    ),
                )
                issues.append(issue)

        return issues
