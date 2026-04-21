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
            WorkflowRunType.REFERENCE_VALIDATION,
        ],
    ),
    CategoryConfig(
        slug="substantive_review",
        label="Substantive Review",
        workflows=[
            # WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            WorkflowRunType.INFERENCE_VALIDATION_V2,
            WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
            WorkflowRunType.RESULTS_EXTRACTION,
            WorkflowRunType.REVIEWER_2,
        ],
    ),
    CategoryConfig(
        slug="technical_compliance",
        label="Editorial and Style Review",
        workflows=[
            WorkflowRunType.ABBREVIATION_SCAN_V2,
            WorkflowRunType.ABOUT_THIS_GER,
            WorkflowRunType.DOCUMENT_STRUCTURE,
            WorkflowRunType.FIGURES_TABLES_CHECK,
        ],
    ),
    CategoryConfig(
        slug="language",
        label="Language",
        workflows=[
            WorkflowRunType.ADVOCACY_TONE,
        ],
    ),
    CategoryConfig(
        slug="research_writing_assistant",
        label="Research & Writing Assistant",
        workflows=[
            WorkflowRunType.LITERATURE_REVIEW,
            WorkflowRunType.CITATION_SUGGESTER,
            WorkflowRunType.LIVE_REPORTS,
        ],
    ),
]
