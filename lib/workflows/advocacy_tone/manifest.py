from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.advocacy_tone.graph import build_advocacy_tone_graph
from lib.workflows.advocacy_tone.state import (
    AdvocacyToneState,
    AdvocacyToneWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState


class AdvocacyToneManifest(
    WorkflowManifest[AdvocacyToneState, AdvocacyToneWorkflowConfig]
):
    type = WorkflowRunType.ADVOCACY_TONE
    name = "Advocacy & Tone"
    description =
        "Does your document use neutral, objective language? Flags advocacy language, trigger words, and subjective tone using fast pattern matching (regex) followed by LLM verification."
    needs_web_search = False
    required_dependencies = [WorkflowRunType.CHUNK_SPLITTING]
    is_experimental = False

    def get_state_type(self) -> Type[AdvocacyToneState]:
        """Get the type of the workflow state."""
        return AdvocacyToneState

    def get_config_type(self) -> Type[AdvocacyToneWorkflowConfig]:
        """Get the type of the workflow config."""
        return AdvocacyToneWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_advocacy_tone_graph()

    async def create_initial_state(
        self,
        config: AdvocacyToneWorkflowConfig,
        existing_states: List[WorkflowState],
        revision: int,
    ) -> AdvocacyToneState:
        """Create and return the initial state of the workflow."""
        return AdvocacyToneState(
            type=WorkflowRunType.ADVOCACY_TONE,
            config=config,
        )

    def convert_state_to_issues(
        self, state: AdvocacyToneState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert AdvocacyToneState to issues for Document Explorer."""
        issues: List[DocumentIssue] = []

        for result in state.results:
            # Only create issues for LLM-confirmed findings
            if result.llm_trigger_words and result.llm_trigger_words.confirmed:
                issues.append(
                    DocumentIssue(
                        title="Trigger Words Detected",
                        description=result.llm_trigger_words.explanation,
                        severity=SeverityEnum.LOW,
                        type=self.type,
                        chunk_indices=[result.chunk_index],
                    )
                )

            if result.llm_advocacy_language and result.llm_advocacy_language.confirmed:
                issues.append(
                    DocumentIssue(
                        title="Advocacy Language Detected",
                        description=result.llm_advocacy_language.explanation,
                        severity=SeverityEnum.MEDIUM,
                        type=self.type,
                        chunk_indices=[result.chunk_index],
                    )
                )

            if result.llm_subjective_tone and result.llm_subjective_tone.confirmed:
                issues.append(
                    DocumentIssue(
                        title="Subjective Tone Detected",
                        description=result.llm_subjective_tone.explanation,
                        severity=SeverityEnum.MEDIUM,
                        type=self.type,
                        chunk_indices=[result.chunk_index],
                    )
                )

        return issues
