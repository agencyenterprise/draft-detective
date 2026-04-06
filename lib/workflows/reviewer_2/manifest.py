from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reviewer_2.graph import build_reviewer_2_graph
from lib.workflows.reviewer_2.state import Reviewer2Config, Reviewer2State
from lib.workflows.util import get_main_file_id
from lib.workflows.workflow_types import WorkflowState


class Reviewer2Manifest(WorkflowManifest[Reviewer2State, Reviewer2Config]):
    type = WorkflowRunType.REVIEWER_2
    name = "Reviewer 2"
    description = (
        "Experimental peer review of the document by a simulated senior researcher, "
        "producing a structured review with strengths, weaknesses, actionable "
        "next steps, and a devil's-advocate rebuttal."
    )
    needs_web_search = False
    is_experimental = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[Reviewer2State]:
        return Reviewer2State

    def get_config_type(self) -> Type[Reviewer2Config]:
        return Reviewer2Config

    def build_graph(self) -> StateGraph:
        return build_reviewer_2_graph()

    async def create_initial_state(
        self,
        config: Reviewer2Config,
        existing_states: List[WorkflowState],
    ) -> Reviewer2State:
        return Reviewer2State(
            type=WorkflowRunType.REVIEWER_2,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self, state: Reviewer2State, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        return []
