from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.results_extraction.graph import build_results_extraction_graph
from lib.workflows.results_extraction.state import (
    ResultsExtractionState,
    ResultsExtractionWorkflowConfig,
)
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class ResultsExtractionManifest(
    WorkflowManifest[ResultsExtractionState, ResultsExtractionWorkflowConfig]
):
    type = WorkflowRunType.RESULTS_EXTRACTION
    name = "Results Extraction"
    description = (
        "Extract main results from the document and assess their reproducibility"
    )
    needs_web_search = False
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

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
        return ResultsExtractionState(
            type=WorkflowRunType.RESULTS_EXTRACTION,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ResultsExtractionState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        return []
