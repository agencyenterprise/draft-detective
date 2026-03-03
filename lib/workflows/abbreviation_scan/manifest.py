"""Manifest for abbreviation scan workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.abbreviation_scan.graph import build_abbreviation_scan_graph
from lib.workflows.abbreviation_scan.state import (
    AbbreviationScanState,
    AbbreviationScanWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id


class AbbreviationScanManifest(
    WorkflowManifest[AbbreviationScanState, AbbreviationScanWorkflowConfig]
):
    type = WorkflowRunType.ABBREVIATION_SCAN
    name = "Abbreviation Scan (Regex-based)"
    description = "Scan the document for abbreviations/acronyms and definition pairs"
    needs_web_search = False
    can_be_triggered_by_user = False
    is_internal = True
    order = 9
    required_dependencies = [WorkflowRunType.CHUNK_SPLITTING]

    def get_state_type(self) -> Type[AbbreviationScanState]:
        return AbbreviationScanState

    def get_config_type(self) -> Type[AbbreviationScanWorkflowConfig]:
        return AbbreviationScanWorkflowConfig

    def build_graph(self) -> StateGraph:
        return build_abbreviation_scan_graph()

    async def create_initial_state(
        self,
        config: AbbreviationScanWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> AbbreviationScanState:
        return AbbreviationScanState(
            type=WorkflowRunType.ABBREVIATION_SCAN,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self, state: AbbreviationScanState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        issues: List[DocumentIssue] = []
        for abbreviation in state.abbreviations:
            if abbreviation.definition:
                issues.append(
                    DocumentIssue(
                        title="Abbreviation defined",
                        description=f'The abbreviation "{abbreviation.abbr}" is defined as "{abbreviation.definition}".',
                        severity=SeverityEnum.NONE,
                        type=self.type,
                        chunk_indices=[abbreviation.chunk_index],
                    )
                )
            else:
                issues.append(
                    DocumentIssue(
                        title="Abbreviation without definition found",
                        description=f"The abbreviation '{abbreviation.abbr}' was found without a definition. Please add a definition for this abbreviation.",
                        severity=SeverityEnum.LOW,
                        type=self.type,
                        chunk_indices=[abbreviation.chunk_index],
                    )
                )
        return issues
