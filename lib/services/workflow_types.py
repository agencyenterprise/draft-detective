"""Service layer for workflow types."""

from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel

from lib.models.user import User, UserRole
from lib.workflows.manifest import QA_SCREENER_WORKFLOWS
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_all_manifests

if TYPE_CHECKING:
    from lib.workflows.manifest import WorkflowManifest

QA_SCREENER_ALLOWED_ROLES = {UserRole.ADMIN, UserRole.RAND}


class WorkflowTypeDescription(BaseModel):
    """Workflow type description for API responses."""

    type: WorkflowRunType
    name: str
    description: str
    needs_web_search: bool
    is_experimental: bool
    is_internal: bool
    can_be_triggered_by_user: bool
    is_qa_screener: bool
    order: int

    @classmethod
    def from_manifest(cls, manifest: "WorkflowManifest") -> "WorkflowTypeDescription":
        return cls(**{f: getattr(manifest, f) for f in cls.model_fields})


def can_user_see_qa_screener(user: Optional[User]) -> bool:
    """Check if a user can see QA Screener workflows."""
    return user is not None and user.role in QA_SCREENER_ALLOWED_ROLES


def get_workflow_types_for_user(user: Optional[User]) -> List[WorkflowTypeDescription]:
    """Get all workflow types visible to a user.

    Filters out QA Screener workflows for users without RAND or ADMIN role.
    """
    can_see_qa_screener = can_user_see_qa_screener(user)

    workflow_types = [
        WorkflowTypeDescription.from_manifest(manifest)
        for manifest in get_all_manifests().values()
        if can_see_qa_screener or manifest.type not in QA_SCREENER_WORKFLOWS
    ]

    return sorted(workflow_types, key=lambda x: x.order)
