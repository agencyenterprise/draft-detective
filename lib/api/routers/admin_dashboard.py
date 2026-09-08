"""Admin usage dashboard endpoints."""

import uuid
from typing import Annotated

import aiotools
from fastapi import APIRouter, Depends, Query

from lib.api.auth import require_admin
from lib.models.user import User
from lib.services.admin_dashboard.ignored_users import get_default_ignored_users
from lib.services.admin_dashboard.models import (
    AdminDashboardResponse,
    DashboardIgnoredUser,
)
from lib.services.admin_dashboard.service import (
    CACHE_TTL_SECONDS,
    get_admin_dashboard,
)

router = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])

# Cache the aggregate (a set of sequential scans over workflow_runs) at the
# endpoint layer, the same way the duration estimates endpoint does. A few
# minutes on figures that count whole days is invisible to the reader, and the
# response says both when it was computed and how long it may be served, so the
# page can tell them what they are looking at.
#
# aiotools.lru_cache wraps async-lru, which caches the in-flight task: callers
# arriving during a miss await the same computation rather than starting their
# own. That is what keeps a refresh-happy admin — or several — down to one set
# of scans per window per interval.
#
# An entry is one (window, ignore list) pair. The UI offers four windows and
# most admins never touch the default ignore list, so the working set is a
# handful; the cap keeps a caller who churns either parameter from growing the
# cache without bound.
_CACHE_MAXSIZE = 32

# A `NOT IN` over more users than this is not a dashboard filter any more. The
# multi-select is meant for a few service accounts and the odd colleague whose
# testing skews the numbers.
_MAX_EXCLUDED_USERS = 50


@aiotools.lru_cache(maxsize=_CACHE_MAXSIZE, expire_after=CACHE_TTL_SECONDS)
async def _cached_dashboard(
    days: int, ignored_user_ids: tuple[uuid.UUID, ...]
) -> AdminDashboardResponse:
    return await get_admin_dashboard(days, ignored_user_ids)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard(
    exclude_user_ids: Annotated[
        list[uuid.UUID],
        Query(
            default_factory=list,
            max_length=_MAX_EXCLUDED_USERS,
            description=(
                "Users to leave out of every figure: their sign-up, their "
                "projects, the runs on those projects and the feedback on or by "
                "them. Repeat the parameter once per user. Nobody is excluded "
                "unless named here; `/api/admin/dashboard/default-ignored-users` "
                "says who the UI names by default."
            ),
        ),
    ],
    days: int = Query(
        default=30,
        ge=1,
        le=730,
        description="Length of the rolling window, in days.",
    ),
    _admin: User = Depends(require_admin),
) -> AdminDashboardResponse:
    """Usage aggregates for the admin dashboard over a rolling window.

    Counts are paired with the equal-length window that preceded them so the UI
    can show a trend. Feedback is reported as counts only; text and authorship
    remain behind the per-project visibility rules of `/api/admin/feedbacks`.

    Served from a short cache (see `_cached_dashboard`); the response carries
    both the moment the figures were computed and the cache window, so the UI
    can say how stale they may be.
    """
    # Sorted and de-duplicated before it becomes a cache key: the same people
    # named in a different order, or twice, are the same figures.
    return await _cached_dashboard(days, tuple(sorted(set(exclude_user_ids))))


@router.get(
    "/dashboard/default-ignored-users", response_model=list[DashboardIgnoredUser]
)
async def get_dashboard_default_ignored_users(
    _admin: User = Depends(require_admin),
) -> list[DashboardIgnoredUser]:
    """The users the dashboard leaves out unless an admin changes the selection.

    Today that is the account the e2e evals run as. The dashboard endpoint
    itself excludes nobody on its own: the UI seeds its multi-select from this
    list and sends the result back as `exclude_user_ids`, so what the admin
    sees selected is exactly what the figures leave out.
    """
    return await get_default_ignored_users()
