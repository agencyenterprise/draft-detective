"""Manifest for human approval workflow."""

from datetime import datetime
from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.human_approval.state import (
    HumanApprovalConfig,
    HumanApprovalState,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.types import WorkflowState


class HumanApprovalManifest(WorkflowManifest[HumanApprovalState, HumanApprovalConfig]):
    """Human-in-the-loop gate that blocks dependent workflows until approved via API."""

    type = WorkflowRunType.HUMAN_APPROVAL
    name = "Human Approval"
    description = "Human-in-the-loop checkpoint that waits for user approval"
    needs_web_search = False
    is_internal = True
    can_be_triggered_by_user = False
    requires_human_trigger = True
    required_dependencies = [WorkflowRunType.REFERENCE_FILE_MATCHING]

    def get_state_type(self) -> Type[HumanApprovalState]:
        return HumanApprovalState

    def get_config_type(self) -> Type[HumanApprovalConfig]:
        return HumanApprovalConfig

    def build_graph(self) -> StateGraph:
        def approve(state: HumanApprovalState) -> dict:
            return {
                "approved": True,
                "approved_at": datetime.utcnow().isoformat(),
            }

        graph = StateGraph(HumanApprovalState)
        graph.add_node("approve", approve)
        graph.set_entry_point("approve")
        graph.set_finish_point("approve")

        return graph

    async def create_initial_state(
        self,
        config: HumanApprovalConfig,
        existing_states: List[WorkflowState],
    ) -> HumanApprovalState:
        return HumanApprovalState(
            type=WorkflowRunType.HUMAN_APPROVAL,
            config=config,
            approved=False,
        )

    def convert_state_to_issues(
        self,
        state: HumanApprovalState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        return []
