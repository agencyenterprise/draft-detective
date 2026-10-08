"""Validation of the inputs picked for a review-assistant output, and the
system prompt a run handed its inputs gets."""

import uuid

import pytest

from lib.services.review_assistant_runs import (
    ReviewAssistantInputs,
    ReviewInputsError,
    _check_slots,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.reviewer_coverage_report.manifest import (
    ReviewerCoverageReportManifest,
)
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentConfig

PLAN = WorkflowRunType.REVISION_PLANNING_SUMMARY
COVERAGE = WorkflowRunType.REVIEWER_COVERAGE_REPORT


def _id() -> str:
    return str(uuid.uuid4())


def test_by_slot_drops_empty_inputs():
    inputs = ReviewAssistantInputs(reviewed_draft="a", reviewer_memos=["b", "c"])
    assert {slot.value: ids for slot, ids in inputs.by_slot().items()} == {
        "reviewed-draft": ["a"],
        "reviewer-memos": ["b", "c"],
    }


def test_plan_runs_on_a_draft_and_memos():
    inputs = ReviewAssistantInputs(reviewed_draft=_id(), reviewer_memos=[_id()])
    _check_slots(PLAN, inputs.by_slot())


def test_coverage_takes_response_memos_as_optional():
    inputs = ReviewAssistantInputs(
        reviewed_draft=_id(), revised_draft=_id(), reviewer_memos=[_id()]
    )
    _check_slots(COVERAGE, inputs.by_slot())
    inputs.response_memos = [_id()]
    _check_slots(COVERAGE, inputs.by_slot())


def test_missing_required_input_is_rejected():
    inputs = ReviewAssistantInputs(reviewed_draft=_id(), reviewer_memos=[_id()])
    with pytest.raises(ReviewInputsError, match="revised-draft"):
        _check_slots(COVERAGE, inputs.by_slot())


def test_input_the_output_does_not_read_is_rejected():
    inputs = ReviewAssistantInputs(
        reviewed_draft=_id(), reviewer_memos=[_id()], response_memos=[_id()]
    )
    with pytest.raises(ReviewInputsError, match="response-memos"):
        _check_slots(PLAN, inputs.by_slot())


def test_a_file_fills_one_input_only():
    same = _id()
    inputs = ReviewAssistantInputs(
        reviewed_draft=same, revised_draft=same, reviewer_memos=[_id()]
    )
    with pytest.raises(ReviewInputsError, match="only one input"):
        _check_slots(COVERAGE, inputs.by_slot())


def test_non_review_output_is_rejected():
    inputs = ReviewAssistantInputs(reviewed_draft=_id(), reviewer_memos=[_id()])
    with pytest.raises(ReviewInputsError, match="not a review-assistant output"):
        _check_slots(WorkflowRunType.DOCUMENT_PROCESSING, inputs.by_slot())


def test_explicit_inputs_switch_the_system_prompt():
    manifest = ReviewerCoverageReportManifest()
    config = SimpleDeepAgentConfig(type=COVERAGE, project_id=_id())
    assert manifest.resolve_system_prompt(config) == manifest.system_prompt

    config.input_files = {"reviewed-draft": [_id()]}
    prompt = manifest.resolve_system_prompt(config)
    assert prompt is not None
    assert "/inputs/revised-draft/" in prompt
    assert "/revisions/" not in prompt
