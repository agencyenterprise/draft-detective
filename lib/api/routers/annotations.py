"""Human annotation endpoints: users judge eval items, admins read the results."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from lib.api.auth import get_current_user, require_admin
from lib.models.user import User
from lib.services.annotations import admin as annotation_admin
from lib.services.annotations import service as annotation_service
from lib.services.annotations.models import (
    AnnotatedItem,
    AnnotationOutcome,
    AnnotationSetStats,
    AnnotationSetSummary,
    AnnotationSubmission,
    AnnotationTask,
)

router = APIRouter(tags=["annotations"])

# A visit skips a handful of items at most; the cap keeps the NOT IN small.
_MAX_SKIPPED = 100


@router.get("/api/annotations/sets", response_model=list[AnnotationSetSummary])
async def list_annotation_sets(
    current_user: User = Depends(get_current_user),
) -> list[AnnotationSetSummary]:
    """The sets a user can annotate, with their progress in each."""
    return await annotation_service.list_sets(current_user)


@router.get("/api/annotations/sets/{slug}/next", response_model=AnnotationTask)
async def get_next_annotation_task(
    slug: str,
    skip: Annotated[list[UUID], Query(default_factory=list, max_length=_MAX_SKIPPED)],
    current_user: User = Depends(get_current_user),
) -> AnnotationTask:
    """The next item for the user to judge, without its reference answers."""
    return await annotation_service.next_task(slug, current_user, skip)


@router.put("/api/annotations/items/{item_id}", response_model=AnnotationOutcome)
async def submit_annotation(
    item_id: UUID,
    submission: AnnotationSubmission,
    current_user: User = Depends(get_current_user),
) -> AnnotationOutcome:
    """Save (or replace) the user's answers. Never reveals the reference answers."""
    return await annotation_service.submit_annotation(item_id, current_user, submission)


@router.get("/api/admin/annotations/sets", response_model=list[AnnotationSetStats])
async def list_annotation_set_stats(
    _admin: User = Depends(require_admin),
) -> list[AnnotationSetStats]:
    """Agreement with the eval datasets for every set."""
    return await annotation_admin.list_set_stats()


@router.get(
    "/api/admin/annotations/sets/{slug}/items", response_model=list[AnnotatedItem]
)
async def list_annotated_items(
    slug: str,
    only_disagreements: bool = False,
    _admin: User = Depends(require_admin),
) -> list[AnnotatedItem]:
    """Every annotated item in a set with its annotations, the most contested first."""
    return await annotation_admin.list_annotated_items(slug, only_disagreements)
