"""Manifest for About Authors validation workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.about_authors.graph import build_about_authors_graph
from lib.workflows.about_authors.state import (
    AboutAuthorsState,
    AboutAuthorsWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState


class AboutAuthorsManifest(
    WorkflowManifest[AboutAuthorsState, AboutAuthorsWorkflowConfig]
):
    type = WorkflowRunType.ABOUT_AUTHORS
    name = "About Authors"
    description = (
        "Validate author biographies against publication rules: "
        "sentence count, position/affiliation, TASP statement, research focus, and highest degree."
    )
    needs_web_search = False
    order = 8
    required_dependencies = [WorkflowRunType.CHUNK_SPLITTING]
    is_experimental = True

    def get_state_type(self) -> Type[AboutAuthorsState]:
        """Get the type of the workflow state."""
        return AboutAuthorsState

    def get_config_type(self) -> Type[AboutAuthorsWorkflowConfig]:
        """Get the type of the workflow config."""
        return AboutAuthorsWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_about_authors_graph()

    async def create_initial_state(
        self,
        config: AboutAuthorsWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> AboutAuthorsState:
        """Create and return the initial state of the workflow."""
        return AboutAuthorsState(
            type=WorkflowRunType.ABOUT_AUTHORS,
            config=config,
        )

    def convert_state_to_issues(
        self, state: AboutAuthorsState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert AboutAuthorsState to issues for Document Explorer."""
        issues: List[DocumentIssue] = []

        for result in state.results:
            if result.overall_passed:
                continue

            # Create issues for each failed rule
            failed_rules = []

            if not result.rule_1_sentence_length.passed:
                failed_rules.append(
                    f"Sentence count: {result.rule_1_sentence_length.explanation}"
                )

            if not result.rule_2_position_affiliation.passed:
                failed_rules.append(
                    f"Position/Affiliation: {result.rule_2_position_affiliation.explanation}"
                )

            if (
                result.rule_3_tasp_statement.applicable
                and not result.rule_3_tasp_statement.passed
            ):
                failed_rules.append(
                    f"TASP Statement: {result.rule_3_tasp_statement.explanation}"
                )

            if not result.rule_4_research_focus.passed:
                failed_rules.append(
                    f"Research Focus: {result.rule_4_research_focus.explanation}"
                )

            if not result.rule_5_highest_degree.passed:
                failed_rules.append(
                    f"Highest Degree: {result.rule_5_highest_degree.explanation}"
                )

            description = f"{result.final_comment}"
            if result.guidance:
                description += f"\n\nGuidance: {result.guidance}"
            description += f"\n\nFailed rules:\n" + "\n".join(f"• {r}" for r in failed_rules)

            # Use first chunk index for navigation
            chunk_index = result.chunk_indices[0] if result.chunk_indices else None

            issues.append(
                DocumentIssue(
                    title=f"Author Bio Issue: {result.author_name}",
                    description=description,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=chunk_index,
                )
            )

        return issues

