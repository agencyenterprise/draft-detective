"""Explicit inputs for the three review-assistant outputs.

The review-assistant workflows normally find their inputs from the project's
layout: the reviewed draft is the latest revision with reviewer memos, the
revised draft is the current revision. A run can instead be handed its inputs
explicitly, one or more project files per slot, which is what lets a user pick
any revision or file for each input. Those files are mounted for the agent at
``/inputs/<slot>/<file_id>.md``, and each manifest's explicit-inputs prompt
points the agent there.
"""

from enum import Enum

from pydantic import BaseModel

from lib.workflows.models import WorkflowRunType


class ReviewInputSlot(str, Enum):
    """One input of a review-assistant output, named as its mount folder."""

    REVIEWED_DRAFT = "reviewed-draft"
    REVISED_DRAFT = "revised-draft"
    REVIEWER_MEMOS = "reviewer-memos"
    RESPONSE_MEMOS = "response-memos"


class ReviewOutputSpec(BaseModel):
    """Which slots an output reads, and which of them it cannot run without."""

    required: list[ReviewInputSlot]
    optional: list[ReviewInputSlot] = []

    @property
    def accepted(self) -> list[ReviewInputSlot]:
        return [*self.required, *self.optional]


REVIEW_OUTPUT_SPECS: dict[WorkflowRunType, ReviewOutputSpec] = {
    WorkflowRunType.REVISION_PLANNING_SUMMARY: ReviewOutputSpec(
        required=[ReviewInputSlot.REVIEWED_DRAFT, ReviewInputSlot.REVIEWER_MEMOS],
    ),
    WorkflowRunType.REVIEWER_RESPONSE_MEMOS: ReviewOutputSpec(
        required=[
            ReviewInputSlot.REVIEWED_DRAFT,
            ReviewInputSlot.REVIEWER_MEMOS,
            ReviewInputSlot.REVISED_DRAFT,
        ],
    ),
    WorkflowRunType.REVIEWER_COVERAGE_REPORT: ReviewOutputSpec(
        required=[
            ReviewInputSlot.REVIEWED_DRAFT,
            ReviewInputSlot.REVIEWER_MEMOS,
            ReviewInputSlot.REVISED_DRAFT,
        ],
        optional=[ReviewInputSlot.RESPONSE_MEMOS],
    ),
}

