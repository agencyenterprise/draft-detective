"""Manifest for abbreviation scan v2 workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.abbreviation_scan_v2.graph import build_abbreviation_scan_v2_graph
from lib.workflows.abbreviation_scan_v2.issues import build_issues
from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationScanV2Config,
    AbbreviationScanV2State,
)
from lib.workflows.chunk_utils import build_analyzed_chunks
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState


class AbbreviationScanV2Manifest(
    WorkflowManifest[AbbreviationScanV2State, AbbreviationScanV2Config]
):
    type = WorkflowRunType.ABBREVIATION_SCAN_V2
    name = "Abbreviation Scan"
    description = (
        "Scan the document for abbreviations and acronyms, "
        "verify each is defined inline at its first occurrence, and check that "
        "all abbreviations are listed in an Abbreviations section."
    )
    needs_web_search = False
    is_internal = False
    is_experimental = False
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[AbbreviationScanV2State]:
        return AbbreviationScanV2State

    def get_config_type(self) -> Type[AbbreviationScanV2Config]:
        return AbbreviationScanV2Config

    def build_graph(self) -> StateGraph:
        return build_abbreviation_scan_v2_graph()

    async def create_initial_state(
        self,
        config: AbbreviationScanV2Config,
        existing_states: List[WorkflowState],
        revision: int,
    ) -> AbbreviationScanV2State:
        return AbbreviationScanV2State(
            type=WorkflowRunType.ABBREVIATION_SCAN_V2,
            config=config,
        )

    def convert_state_to_issues(
        self, state: AbbreviationScanV2State, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        chunks = build_analyzed_chunks(other_states)
        return build_issues(state, chunks)
