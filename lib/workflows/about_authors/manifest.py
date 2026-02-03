"""Manifest for About Authors validation workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.about_authors.constants import RULE_FIELDS, RULE_METADATA
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
    order = 11  # QA Screener group (10-12)
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

        if not state.results:
            issues.append(
                DocumentIssue(
                    title='No "About the Authors" section found',
                    description=f'We could not find an "About the Authors" or "Author Biographies" section. Author validation requires a section containing author biography paragraphs. Please ensure your document contains an appropriately titled section and run "{self.name}" analysis again.',
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=0,
                )
            )

        for result in state.results:
            if result.overall_passed:
                continue

            # Build failed rules using centralized metadata
            failed_rules = []
            for field in RULE_FIELDS:
                rule_check = getattr(result, field)
                if rule_check.applicable and not rule_check.passed:
                    label = RULE_METADATA[field]["short_name"]
                    failed_rules.append(f"{label}: {rule_check.explanation}")

            description = f"{result.final_comment}"
            if result.guidance:
                description += f"\n\nGuidance: {result.guidance}"
            description += "\n\nFailed rules:\n" + "\n".join(
                f"• {r}" for r in failed_rules
            )

            # Use all chunk indices for highlighting, first one for backward compat
            chunk_indices = result.chunk_indices if result.chunk_indices else []
            chunk_index = chunk_indices[0] if chunk_indices else None

            issues.append(
                DocumentIssue(
                    title=f"Author Bio Issue: {result.author_name}",
                    description=description,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=chunk_index,
                    chunk_indices=chunk_indices,
                )
            )

        return issues
