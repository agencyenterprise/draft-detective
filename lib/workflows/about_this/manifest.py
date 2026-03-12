"""Manifest for About This (Preface) validation workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.about_this.constants import REQUIREMENT_FIELDS, REQUIREMENT_METADATA
from lib.workflows.about_this.graph import build_about_this_graph
from lib.workflows.about_this.state import (
    AboutThisState,
    AboutThisWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState


class AboutThisManifest(WorkflowManifest[AboutThisState, AboutThisWorkflowConfig]):
    type = WorkflowRunType.ABOUT_THIS
    name = "About This (Preface)"
    description = (
        "Validate preface/introduction sections against publication requirements: "
        "context, objectives, relationship to RAND work, intended audience, "
        "CAST boilerplate, and funding statement."
    )
    needs_web_search = False
    order = 12  # QA Screener group (10-12)
    required_dependencies = [WorkflowRunType.CHUNK_SPLITTING]
    is_experimental = True
    is_internal = True
    can_be_triggered_by_user = False

    def get_state_type(self) -> Type[AboutThisState]:
        """Get the type of the workflow state."""
        return AboutThisState

    def get_config_type(self) -> Type[AboutThisWorkflowConfig]:
        """Get the type of the workflow config."""
        return AboutThisWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_about_this_graph()

    async def create_initial_state(
        self,
        config: AboutThisWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> AboutThisState:
        """Create and return the initial state of the workflow."""
        return AboutThisState(
            type=WorkflowRunType.ABOUT_THIS,
            config=config,
        )

    def convert_state_to_issues(
        self, state: AboutThisState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert AboutThisState to issues for Document Explorer."""
        issues: List[DocumentIssue] = []

        if not state.found_section:
            issues.append(
                DocumentIssue(
                    title="No preface section found",
                    type=self.type,
                    description=f'We could not find an "About This Report", "Preface", or similar introductory section. Preface validation requires a clearly titled section heading. Please ensure your document contains an appropriately titled section and run "{self.name}" analysis again.',
                    severity=SeverityEnum.MEDIUM,
                    chunk_indices=[0],
                )
            )
            return issues

        # Create issues for failed requirements
        for field in REQUIREMENT_FIELDS:
            requirement_result = getattr(state, field, None)
            if requirement_result is None:
                continue

            if not requirement_result.passed:
                meta = REQUIREMENT_METADATA[field]
                issues.append(
                    DocumentIssue(
                        title=f"Preface: {meta['name']} Missing",
                        type=self.type,
                        description=(
                            f"{meta['description']}\n\n"
                            f"Result: {requirement_result.explanation}"
                        ),
                        severity=SeverityEnum.MEDIUM,
                    )
                )

        return issues
