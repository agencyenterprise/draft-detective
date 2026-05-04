from typing import List, Type, cast

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph, RunnableConfig

from lib.agents.reference_validator_v2 import ReferenceValidationFinalResultV2
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_validation_v2.graph import (
    build_reference_validation_v2_graph,
)
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2State,
    ReferenceValidationV2Status,
    ReferenceValidationV2WorkflowConfig,
)
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_state_by_type


_FINAL_RESULT_SEVERITY: dict[ReferenceValidationFinalResultV2, SeverityEnum] = {
    ReferenceValidationFinalResultV2.CORRECT: SeverityEnum.NONE,
    ReferenceValidationFinalResultV2.MISSING_FIELDS: SeverityEnum.MEDIUM,
    ReferenceValidationFinalResultV2.INCORRECT_FIELDS: SeverityEnum.HIGH,
}

_FINAL_RESULT_TITLE: dict[ReferenceValidationFinalResultV2, str] = {
    ReferenceValidationFinalResultV2.CORRECT: "Valid reference",
    ReferenceValidationFinalResultV2.MISSING_FIELDS: "Reference is missing fields",
    ReferenceValidationFinalResultV2.INCORRECT_FIELDS: "Reference has incorrect fields",
}


class ReferenceValidationV2Manifest(
    WorkflowManifest[ReferenceValidationV2State, ReferenceValidationV2WorkflowConfig]
):
    type = WorkflowRunType.REFERENCE_VALIDATION_V2
    name = "Reference Error Checker"
    description = "Are your references accurate? Uses web search to check each citation exists online and that the author, title, publisher, and year match public sources. Useful for catching typos or hallucinated references."
    needs_web_search = True
    required_dependencies = [WorkflowRunType.REFERENCE_EXTRACTION]

    def get_state_type(self) -> Type[ReferenceValidationV2State]:
        return ReferenceValidationV2State

    def get_config_type(self) -> Type[ReferenceValidationV2WorkflowConfig]:
        return ReferenceValidationV2WorkflowConfig

    def build_graph(self) -> StateGraph:
        return build_reference_validation_v2_graph()

    async def on_cancel(
        self,
        state: ReferenceValidationV2State,
        app: CompiledStateGraph,
        config: RunnableConfig,
    ) -> None:
        """Mark any pending validation items as cancelled so they don't show as in-progress."""
        updated = [
            (
                item.model_copy(
                    update={"status": ReferenceValidationV2Status.CANCELLED}
                )
                if item.status == ReferenceValidationV2Status.PENDING
                else item
            )
            for item in state.reference_validations
        ]
        await app.aupdate_state(
            config, {"reference_validations": updated}, as_node="finalize_validations"
        )

    async def create_initial_state(
        self,
        config: ReferenceValidationV2WorkflowConfig,
        existing_states: List[WorkflowState],
        revision: int,
    ) -> ReferenceValidationV2State:
        return ReferenceValidationV2State(
            type=WorkflowRunType.REFERENCE_VALIDATION_V2,
            config=config,
        )

    def convert_state_to_issues(
        self, state: ReferenceValidationV2State, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ReferenceValidationV2State to issues."""

        issues: List[DocumentIssue] = []

        ref_extraction_state = get_state_by_type(
            WorkflowRunType.REFERENCE_EXTRACTION, other_states
        )
        ref_extraction_state = (
            cast(ReferenceExtractionState, ref_extraction_state)
            if ref_extraction_state
            else None
        )

        ref_by_id = (
            {ref.id: ref for ref in ref_extraction_state.extracted_references}
            if ref_extraction_state
            else {}
        )

        for validation in state.reference_validations:
            if validation.status != ReferenceValidationV2Status.COMPLETED:
                continue

            if validation.validation_result is None:
                continue

            result = validation.validation_result
            ref = ref_by_id.get(validation.reference_id)
            severity = _FINAL_RESULT_SEVERITY[result.final_result]
            title = _FINAL_RESULT_TITLE[result.final_result]

            field_validations = "\n\n".join(
                [
                    f"- **{item.category.value.capitalize()}**: {item.problem_type.value.capitalize()}\n\n\t*Current*: {item.current_value or "-"}\n\n\t*Suggested*: {item.suggested_value}"
                    for item in result.bibliography_field_validations
                ]
            )

            issue = DocumentIssue(
                title=title,
                description=f"> {result.original_reference}",
                severity=severity,
                type=self.type,
                start_line=ref.start_line if ref else None,
                end_line=ref.end_line if ref else None,
                long_description=f"{f'### Suggested updated reference\n\n> {result.updated_reference}' if result.updated_reference else ''}\n\n### Field validations\n\n{field_validations}\n\n### Reasoning\n\n{result.reasoning}",
                suggested_action=result.suggested_action or None,
            )
            issues.append(issue)

        return issues
