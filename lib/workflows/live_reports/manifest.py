from typing import List, Type

from langgraph.graph import StateGraph

from lib.agents.evidence_weighter import EvidenceWeighterRecommendedAction
from lib.workflows.live_reports.graph import build_live_reports_graph
from lib.workflows.live_reports.state import LiveReportsState, LiveReportsWorkflowConfig
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class LiveReportsManifest(
    WorkflowManifest[LiveReportsState, LiveReportsWorkflowConfig]
):
    type = WorkflowRunType.LIVE_REPORTS
    name = "Live Reports"
    description = "Have any of your findings been updated or contradicted by newer research? Searches the web for sources published after your document's publish date that may update or challenge your claims. Generates an addendum containing any new evidence."
    needs_web_search = True
    is_experimental = True
    required_dependencies = [
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.CITATION_DETECTION,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
    ]

    def get_state_type(self) -> Type[LiveReportsState]:
        """Get the type of the workflow state."""
        return LiveReportsState

    def get_config_type(self) -> Type[LiveReportsWorkflowConfig]:
        """Get the type of the workflow config."""
        return LiveReportsWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_live_reports_graph()

    async def create_initial_state(
        self,
        config: LiveReportsWorkflowConfig,
        existing_states: List[WorkflowState],
        revision: int,
    ) -> LiveReportsState:
        """Create and return the initial state of the workflow."""

        return LiveReportsState(
            type=WorkflowRunType.LIVE_REPORTS,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self, state: LiveReportsState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert LiveReportsState to issues."""
        issues: List[DocumentIssue] = []

        for live_report in state.live_reports_analysis:
            if (
                live_report.claim_update_action
                == EvidenceWeighterRecommendedAction.ADD_CITATION
            ):
                issue = DocumentIssue(
                    title="Additional Citation Recommended",
                    description=live_report.rationale,
                    severity=SeverityEnum.MEDIUM,
                    type=self.type,
                    chunk_indices=[live_report.chunk_index],
                )
                issues.append(issue)
            elif (
                live_report.claim_update_action
                == EvidenceWeighterRecommendedAction.UPDATE_CLAIM
            ):
                issue = DocumentIssue(
                    title="Claim Update Recommended",
                    description=live_report.rationale,
                    severity=SeverityEnum.MEDIUM,
                    type=self.type,
                    chunk_indices=[live_report.chunk_index],
                )
                issues.append(issue)

        return issues
