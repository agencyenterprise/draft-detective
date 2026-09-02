"""Service layer for workflow types."""

from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.workflows.categories import WORKFLOW_DISPLAY_CONFIG
from lib.services.workflow_gates import get_effective_gates
from lib.workflows.models import WorkflowGate, WorkflowRunType
from lib.workflows.registry import get_all_manifests

if TYPE_CHECKING:
    from lib.workflows.manifest import WorkflowManifest

# Derived map: workflow type → category slug, built once from WORKFLOW_DISPLAY_CONFIG.
_WORKFLOW_CATEGORY_MAP: dict[WorkflowRunType, str] = {
    wf_type: category.slug
    for category in WORKFLOW_DISPLAY_CONFIG
    for wf_type in category.workflows
}

# The assessments the picker can actually offer, in display order. Category
# membership is what puts a workflow in the picker (see WORKFLOW_DISPLAY_CONFIG),
# so this doubles as the filter that turns a project's raw workflow_runs rows
# back into the selection the user made: everything else on a project — the
# internal workflows and the dependencies pulled in by
# resolve_workflow_dependencies — is absent from every category.
_PICKER_WORKFLOW_TYPES: list[WorkflowRunType] = list(_WORKFLOW_CATEGORY_MAP)


class WorkflowTypeDescription(BaseModel):
    """Workflow type description for API responses."""

    type: WorkflowRunType
    name: str
    description: str
    needs_web_search: bool
    is_experimental: bool
    is_internal: bool
    category: str
    # Consents the user must give before this workflow runs, including those
    # inherited from its required dependencies. A run of a gated workflow sits
    # in AWAITING_APPROVAL until every gate is approved for the revision.
    gates: list[WorkflowGate]

    @classmethod
    def from_manifest(cls, manifest: "WorkflowManifest") -> "WorkflowTypeDescription":
        derived = {"category", "gates"}
        fields = {f: getattr(manifest, f) for f in cls.model_fields if f not in derived}
        fields["category"] = _WORKFLOW_CATEGORY_MAP.get(manifest.type, "internal")
        fields["gates"] = get_effective_gates(manifest.type)
        return cls(**fields)


class WorkflowCategoryOrder(BaseModel):
    """Ordered category entry: slug, label, and ordered list of workflow type slugs."""

    slug: str
    label: str
    workflows: list[WorkflowRunType]


class WorkflowTypesResponse(BaseModel):
    """Combined response: flat workflow details plus the ordered category display config."""

    workflow_types: list[WorkflowTypeDescription]
    categories: list[WorkflowCategoryOrder]


class RecentWorkflowSelectionResponse(BaseModel):
    """The assessments a user picked most recently, for pre-checking the wizard."""

    workflow_types: list[WorkflowRunType]


def get_all_workflow_types() -> WorkflowTypesResponse:
    """Get all workflow types and the ordered category display config.

    The listing is the same for every caller; experimental workflows are hidden
    client-side based on the user's own preference, not filtered here.
    """
    workflow_types = [
        WorkflowTypeDescription.from_manifest(manifest)
        for manifest in get_all_manifests().values()
    ]
    categories = [
        WorkflowCategoryOrder(slug=cat.slug, label=cat.label, workflows=cat.workflows)
        for cat in WORKFLOW_DISPLAY_CONFIG
    ]

    return WorkflowTypesResponse(workflow_types=workflow_types, categories=categories)


async def get_recent_workflow_selection(user: User) -> RecentWorkflowSelectionResponse:
    """The assessments this user ran on their most recent project.

    Lets the new-project wizard open on the set the user actually reaches for
    instead of a fixed default. Nothing persists a "selection", so it is
    reconstructed from the workflow_runs rows and narrowed to the assessments the
    picker offers (see `_PICKER_WORKFLOW_TYPES`).

    Projects with no picker-visible run are skipped, which is what keeps the
    wizard's own freshly created project — it exists, and document processing may
    already have started on it, before the assessment step renders — from
    shadowing the previous one. Every revision and every run status counts:
    starting an assessment is the signal, not whether it finished.

    Returns an empty list when the user has no qualifying project; callers decide
    what to fall back to.
    """
    picker_types = [wf_type.value for wf_type in _PICKER_WORKFLOW_TYPES]

    async with get_async_db_session() as session:
        latest_project_stmt = (
            select(col(Project.id))
            .join(WorkflowRun, col(WorkflowRun.project_id) == col(Project.id))
            .where(
                col(Project.user_id) == user.id,
                col(WorkflowRun.type).in_(picker_types),
            )
            .order_by(col(Project.created_at).desc())
            .limit(1)
        )
        project_id = (await session.execute(latest_project_stmt)).scalars().first()
        if project_id is None:
            return RecentWorkflowSelectionResponse(workflow_types=[])

        types_stmt = (
            select(col(WorkflowRun.type))
            .where(
                col(WorkflowRun.project_id) == project_id,
                col(WorkflowRun.type).in_(picker_types),
            )
            .distinct()
        )
        # `type` is a plain String column, so rows come back as raw strings.
        # Comparing on `.value` rather than the enum member matters: str-Enum
        # hashes by member *name*, so `member in {"some_value"}` is always False.
        found = {
            str(row) for row in (await session.execute(types_stmt)).scalars().all()
        }

    # Ordered by the display config so the response is deterministic.
    return RecentWorkflowSelectionResponse(
        workflow_types=[
            wf_type for wf_type in _PICKER_WORKFLOW_TYPES if wf_type.value in found
        ]
    )
