"""Assessment presets: named sets of workflows the picker can select in one go.

A preset is for a group of people who always run the same checks, such as an
editorial department, so nobody has to remember which of a dozen assessments
are theirs. Picking a preset replaces the selection with its set; the picker
shows the preset as active while the selection matches it.

Hand-written workflows join a preset by being listed here. A skill-declared
workflow names its presets in its frontmatter (``presets: [editorial_review]``)
and is appended to them by ``lib/services/workflow_types.py``, so adding a
skill to a department's set needs no code change.

To reorder presets: change the order of entries in WORKFLOW_PRESETS. Workflows
within a preset are shown in picker order regardless of the order here.
"""

from typing import NamedTuple

from lib.workflows.models import WorkflowRunType


class PresetConfig(NamedTuple):
    slug: str
    label: str
    description: str
    workflows: list[WorkflowRunType]


WORKFLOW_PRESETS: list[PresetConfig] = [
    PresetConfig(
        slug="standard_review",
        label="Standard Review",
        description=(
            "The checks most drafts start with: accurate references, neutral "
            "language, and recommendations the findings support."
        ),
        workflows=[
            WorkflowRunType.REFERENCE_VALIDATION_V2,
            WorkflowRunType.ADVOCACY_TONE_V2,
            WorkflowRunType.RECOMMENDATION_CHECK,
        ],
    ),
    PresetConfig(
        slug="editorial_review",
        label="Editorial Review",
        description=(
            "The editorial department's checks: who does what, every sentence "
            "earning its length, one voice throughout, headers that carry the "
            "point, and neutral tone."
        ),
        # The skill-declared checks (active voice, concision and precision,
        # writing consistency, headers and skimmability) add themselves from
        # their frontmatter.
        workflows=[
            WorkflowRunType.ADVOCACY_TONE_V2,
        ],
    ),
]
