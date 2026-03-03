from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.inference_validation_v2.graph import (
    build_inference_validation_v2_graph,
)
from lib.workflows.inference_validation_v2.state import (
    InferenceValidationV2State,
    InferenceValidationV2WorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class InferenceValidationV2Manifest(
    WorkflowManifest[InferenceValidationV2State, InferenceValidationV2WorkflowConfig]
):
    type = WorkflowRunType.INFERENCE_VALIDATION_V2
    name = "Inference Validation"
    description = "Analyze the full document for invalid inferences. Identifies logical fallacies, unsupported conclusions, and faulty reasoning. Each finding includes the key sentence, argument analysis, and suggested correction."
    needs_web_search = False
    is_experimental = False
    can_be_triggered_by_user = True
    order = 4
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[InferenceValidationV2State]:
        """Get the type of the workflow state."""
        return InferenceValidationV2State

    def get_config_type(self) -> Type[InferenceValidationV2WorkflowConfig]:
        """Get the type of the workflow config."""
        return InferenceValidationV2WorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_inference_validation_v2_graph()

    async def create_initial_state(
        self,
        config: InferenceValidationV2WorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> InferenceValidationV2State:
        """Create and return the initial state of the workflow."""

        return InferenceValidationV2State(
            type=WorkflowRunType.INFERENCE_VALIDATION_V2,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: InferenceValidationV2State,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert InferenceValidationV2State to issues."""
        issues: List[DocumentIssue] = []

        if state.inference_results is None:
            return issues

        for analysis in state.inference_results.results:
            if not analysis.inference_validity:
                description = (
                    analysis.short_form_argument_analysis
                    or analysis.long_form_argument_analysis
                )

                issues.append(
                    DocumentIssue(
                        title="Invalid Inference",
                        type=self.type,
                        description=description,
                        severity=analysis.severity,
                        chunk_indices=analysis.chunk_indices,
                        long_description=f"# Key Sentence\n\n> {analysis.key_sentence}\n\n# Detailed Analysis\n\n{analysis.long_form_argument_analysis}\n\n# Suggested Action\n\n{analysis.suggested_action}",
                    )
                )

        return issues
