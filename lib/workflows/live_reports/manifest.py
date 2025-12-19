from typing import List, Type

from langgraph.graph import StateGraph

from lib.agents.evidence_weighter import EvidenceWeighterRecommendedAction
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.live_reports.graph import build_live_reports_graph
from lib.workflows.live_reports.state import LiveReportsState, LiveReportsWorkflowConfig
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class LiveReportsManifest(
    WorkflowManifest[LiveReportsState, LiveReportsWorkflowConfig]
):
    type = WorkflowRunType.LIVE_REPORTS
    name = "Live Reports"
    description = "Analyze claims for updates based on references published after the document date. Performs web search to find new relevant literature, looking only for literature published after the document publication date."
    needs_web_search = True
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

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
    ) -> LiveReportsState:
        """Create and return the initial state of the workflow."""
        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        # Carry over optional context from the claim workflow if not provided
        if config.domain is None:
            config.domain = claim_state.config.domain
        if config.target_audience is None:
            config.target_audience = claim_state.config.target_audience

        return LiveReportsState(
            config=config,
            file=claim_state.file,
            references=claim_state.references,
            chunks=claim_state.chunks,
            main_document_summary=claim_state.main_document_summary,
        )

    def convert_state_to_issues(
        self, state: LiveReportsState, claim_state: ClaimSubstantiatorState
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
                    chunk_index=live_report.chunk_index,
                    claim_index=live_report.claim_index,
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
                    chunk_index=live_report.chunk_index,
                    claim_index=live_report.claim_index,
                )
                issues.append(issue)

        return issues
