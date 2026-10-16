import builtins

from langgraph.graph import StateGraph

from lib.services.files.service import get_main_file_id
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reviewer_2.graph import build_reviewer_2_graph
from lib.workflows.reviewer_2.state import Reviewer2Config, Reviewer2State
from lib.workflows.workflow_types import WorkflowState


class Reviewer2Manifest(WorkflowManifest[Reviewer2State, Reviewer2Config]):
    type = WorkflowRunType.REVIEWER_2
    name = "Reviewer 2"
    description = "Simulates a full peer review with a one-shot prompt, returning a structured critique with strengths, weaknesses, actionable next steps, and a devil's-advocate rebuttal."

    needs_web_search = False
    is_experimental = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> builtins.type[Reviewer2State]:
        return Reviewer2State

    def get_config_type(self) -> builtins.type[Reviewer2Config]:
        return Reviewer2Config

    def build_graph(self) -> StateGraph:
        return build_reviewer_2_graph()

    async def create_initial_state(
        self,
        config: Reviewer2Config,
        existing_states: list[WorkflowState],
        revision: int,
        prior_self_state: Reviewer2State | None = None,
    ) -> Reviewer2State:
        return Reviewer2State(
            type=WorkflowRunType.REVIEWER_2,
            config=config,
            file_id=await get_main_file_id(config.project_id, revision),
        )

    def convert_state_to_issues(
        self, state: Reviewer2State, other_states: list[WorkflowState]
    ) -> list[DocumentIssue]:
        return []
