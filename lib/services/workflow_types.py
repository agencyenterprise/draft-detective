"""Service layer for workflow types."""

from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel

from lib.models.user import User, UserRole
from lib.workflows.categories import WORKFLOW_DISPLAY_CONFIG
from lib.workflows.manifest import QA_SCREENER_WORKFLOWS
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_all_manifests

if TYPE_CHECKING:
    from lib.workflows.manifest import WorkflowManifest

QA_SCREENER_ALLOWED_ROLES = {UserRole.ADMIN, UserRole.RAND}

# Derived map: workflow type → category slug, built once from WORKFLOW_DISPLAY_CONFIG.
_WORKFLOW_CATEGORY_MAP: dict[WorkflowRunType, str] = {
    wf_type: category.slug
    for category in WORKFLOW_DISPLAY_CONFIG
    for wf_type in category.workflows
}


class WorkflowTypeDescription(BaseModel):
    """Workflow type description for API responses."""

    type: WorkflowRunType
    name: str
    description: str
    needs_web_search: bool
    is_experimental: bool
    is_internal: bool
    is_qa_screener: bool
    category: str

    @classmethod
    def from_manifest(cls, manifest: "WorkflowManifest") -> "WorkflowTypeDescription":
        fields = {f: getattr(manifest, f) for f in cls.model_fields if f != "category"}
        fields["category"] = _WORKFLOW_CATEGORY_MAP.get(manifest.type, "internal")
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


def can_user_see_qa_screener(user: Optional[User]) -> bool:
    """Check if a user can see QA Screener workflows."""
    return user is not None and user.role in QA_SCREENER_ALLOWED_ROLES


def get_workflow_types_for_user(user: Optional[User]) -> WorkflowTypesResponse:
    """Get all workflow types and ordered category config visible to a user.

    Filters out QA Screener workflows for users without RAND or ADMIN role.
    """
    can_see_qa_screener = can_user_see_qa_screener(user)
    hidden_types = set() if can_see_qa_screener else QA_SCREENER_WORKFLOWS

    workflow_types = [
        WorkflowTypeDescription.from_manifest(manifest)
        for manifest in get_all_manifests().values()
        if manifest.type not in hidden_types
    ]
    categories = [
        WorkflowCategoryOrder(
            slug=cat.slug,
            label=cat.label,
            workflows=[wf for wf in cat.workflows if wf not in hidden_types],
        )
        for cat in WORKFLOW_DISPLAY_CONFIG
    ]

    return WorkflowTypesResponse(workflow_types=workflow_types, categories=categories)
