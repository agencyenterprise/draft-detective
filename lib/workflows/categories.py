"""Workflow display configuration.

This module defines the single source of truth for:
- Which categories exist, their labels, and their display order
- Which workflows belong to each category and in what order within it

To reorder categories: change the order of entries in WORKFLOW_DISPLAY_CONFIG.
To reorder workflows within a category: change the order of the inner list.
"""

from typing import NamedTuple

from lib.workflows.models import WorkflowRunType


class CategoryConfig(NamedTuple):
    slug: str
    label: str
    workflows: list[WorkflowRunType]


WORKFLOW_DISPLAY_CONFIG: list[CategoryConfig] = [
    CategoryConfig(
        slug="citation_check",
        label="Citation Check",
        workflows=[
            WorkflowRunType.REFERENCE_VALIDATION_V2,
        ],
    ),
    CategoryConfig(
        slug="substantive_review",
        label="Substantive Review",
        workflows=[
            WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            WorkflowRunType.INFERENCE_VALIDATION_V2,
            WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
            WorkflowRunType.RESULTS_EXTRACTION,
            WorkflowRunType.REVIEWER_2,
            WorkflowRunType.RECOMMENDATION_CHECK,
        ],
    ),
    CategoryConfig(
        slug="technical_compliance",
        label="Editorial and Style Review",
        workflows=[
            WorkflowRunType.ABBREVIATION_SCAN_V2,
            WorkflowRunType.FIGURES_TABLES_CHECK,
        ],
    ),
    CategoryConfig(
        slug="language",
        label="Language",
        workflows=[
            WorkflowRunType.ADVOCACY_TONE_V2,
        ],
    ),
    # REVIEW_ASSISTANT is deliberately absent. The Review Assistant tab starts it
    # with the outputs and documents the author picked, and a run without them
    # has nothing to read. Leaving it out of every category is what keeps it out
    # of the assessment picker.
    # ABOUT_THIS_GER and DOCUMENT_STRUCTURE are deliberately absent too. Structural
    # Checks (GER), declared by skills/structural-checks-ger/SKILL.md, runs their rules
    # in one check and replaces both in the picker. They stay registered, so existing
    # runs still list and render and the API can still start them by type.
    # The Research & Writing Assistant workflows (LITERATURE_REVIEW_V2 and
    # LIVE_REPORTS_V2) are deliberately absent. Draft Detective is positioned as a
    # suite of checks that review a draft the author already has; these instead go
    # looking for new literature, which is a different product, so they are kept
    # out of the assessment picker. As with the peer-review workflows they stay
    # registered: existing runs still list and render, and the API, MCP, and eval
    # suites can still start them by type.
]
