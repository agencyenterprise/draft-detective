import aiotools
from fastapi import APIRouter, Depends

from lib.api.auth import get_current_user, get_current_user_optional
from lib.models.user import User
from lib.services.workflow_duration_estimates import (
    WorkflowDurationEstimatesResponse,
    get_workflow_duration_estimates,
)
from lib.services.workflow_types import (
    RecentWorkflowSelectionResponse,
    WorkflowTypesResponse,
    get_all_workflow_types,
    get_recent_workflow_selection,
)

router = APIRouter(tags=["workflow-types"])

# Cache the duration-estimates aggregate (a full workflow_runs scan) at the
# endpoint layer. aiotools.lru_cache is functools.lru_cache for coroutines and
# adds a TTL, so the heavy query runs at most once per hour. The estimate is
# global (the service ignores project_id), so the cache holds a single entry:
# keying it on the caller's project_id would let any new id force a fresh scan.
# Key it on project_id again only once the service uses it, and check the
# caller's access to that project before it reaches the cache.
_ESTIMATES_CACHE_TTL_SECONDS = 3600


@aiotools.lru_cache(maxsize=1, expire_after=_ESTIMATES_CACHE_TTL_SECONDS)
async def _cached_duration_estimates() -> WorkflowDurationEstimatesResponse:
    return await get_workflow_duration_estimates()


@router.get("/api/workflow-types", response_model=WorkflowTypesResponse)
async def get_workflow_types():
    """List available workflow types and the ordered category display config."""
    return get_all_workflow_types()


@router.get(
    "/api/workflow-types/recent-selection",
    response_model=RecentWorkflowSelectionResponse,
)
async def get_recent_selection(user: User = Depends(get_current_user)):
    """
    Assessments this user ran on their most recent project.

    Seeds the new-project wizard's pre-selection with what the user actually
    reaches for. Unlike the listing above this is per-user, so it requires auth.
    Deliberately uncached: it is two indexed queries, and it has to reflect the
    project the user just finished.
    """
    return await get_recent_workflow_selection(user)


@router.get(
    "/api/workflow-types/duration-estimates",
    response_model=WorkflowDurationEstimatesResponse,
)
async def get_duration_estimates(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
):
    """
    Estimated run duration for every workflow type, derived from past runs.

    Lets the UI show a ballpark "how long will this take" before a workflow is
    started. `project_id` is accepted for future project-specific refinement but
    is not yet factored into the estimate, nor into the cache key. The response
    is cached for an hour at the endpoint layer (see `_cached_duration_estimates`).
    """
    return await _cached_duration_estimates()
