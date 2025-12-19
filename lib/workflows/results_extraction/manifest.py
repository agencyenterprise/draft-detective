from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.results_extraction.graph import build_results_extraction_graph
from lib.workflows.results_extraction.state import (
    ResultsExtractionState,
    ResultsExtractionWorkflowConfig,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class ResultsExtractionManifest(
    WorkflowManifest[ResultsExtractionState, ResultsExtractionWorkflowConfig]
):
    type = WorkflowRunType.RESULTS_EXTRACTION
    name = "Results Extraction"
    description = (
        "Extract main results from the document and assess their reproducibility"
    )
    needs_web_search = False

    def get_state_type(self) -> Type[ResultsExtractionState]:
        return ResultsExtractionState

    def get_config_type(self) -> Type[ResultsExtractionWorkflowConfig]:
        return ResultsExtractionWorkflowConfig

    def build_graph(self) -> StateGraph:
        return build_results_extraction_graph()

    async def create_initial_state(
        self,
        config: ResultsExtractionWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ResultsExtractionState:
        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )
        return ResultsExtractionState(file=claim_state.file)

    def convert_state_to_issues(
        self,
        state: ResultsExtractionState,
        claim_state: ClaimSubstantiatorState,
    ) -> List[DocumentIssue]:
        return []
