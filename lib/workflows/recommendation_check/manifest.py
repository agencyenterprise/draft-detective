"""Manifest for the Recommendation Check workflow.

Verifies that recommendations made in the document are directly supported by
the findings/evidence presented elsewhere in the same document, and that they
are actionable, say who should act, and are few enough to matter (RAND EEI
"Writing for Impact" item 8). Complements citation-grounding workflows: those
check that claims are backed by external sources; this one checks that
recommendations are backed by the document's own findings.

The rules checked live in the `recommendation-check` skill
(`skills/recommendation-check/SKILL.md`), which is the single source of truth.
"""

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest


class RecommendationCheckManifest(SimpleDeepAgentManifest):
    """Checks that recommendations are supported by the document's own findings and actionable."""

    type = WorkflowRunType.RECOMMENDATION_CHECK
    name = "Recommendation Check"
    description = (
        "Are the document's recommendations supported by its own findings, "
        "and can a reader act on them? Flags recommendations whose evidence is "
        "missing, weak, indirect or contradictory, recommendations that are "
        "vague or do not say who should act, and lists of more than three."
    )
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = True

    skill = "recommendation-check"

    # A recommendation's supporting finding is sometimes only in a figure.
    view_images = True
