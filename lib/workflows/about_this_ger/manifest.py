"""Manifest for About This (GER) workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.about_this_ger.graph import build_about_this_ger_graph
from lib.workflows.about_this_ger.state import (
    AboutThisGerConfig,
    AboutThisGerState,
    AgentCheckResult,
)
from lib.workflows.chunk_utils import build_analyzed_chunks
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.simple_deep_agent.types import issues_from_agent_result
from lib.workflows.workflow_types import WorkflowState


class AboutThisGerManifest(WorkflowManifest[AboutThisGerState, AboutThisGerConfig]):
    type = WorkflowRunType.ABOUT_THIS_GER
    name = "About This (GER)"
    description = (
        "Validates the preface/introduction and author biography sections "
        "against publication requirements using deep-agent analysis."
    )
    needs_web_search = False
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = False

    def get_state_type(self) -> Type[AboutThisGerState]:
        return AboutThisGerState

    def get_config_type(self) -> Type[AboutThisGerConfig]:
        return AboutThisGerConfig

    def build_graph(self) -> StateGraph:
        return build_about_this_ger_graph()

    async def create_initial_state(
        self,
        config: AboutThisGerConfig,
        existing_states: List[WorkflowState],
        revision: int,
    ) -> AboutThisGerState:
        return AboutThisGerState(
            type=WorkflowRunType.ABOUT_THIS_GER,
            config=config,
        )

    def convert_state_to_issues(
        self, state: AboutThisGerState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        chunks = build_analyzed_chunks(other_states)
        issues: List[DocumentIssue] = []

        if state.preface_result is not None:
            issues.extend(
                issues_from_agent_result(state.preface_result, self.type, chunks)
            )

        if state.authors_result is not None:
            issues.extend(
                issues_from_agent_result(state.authors_result, self.type, chunks)
            )

        return issues
