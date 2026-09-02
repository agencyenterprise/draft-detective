"""Response models for the admin usage dashboard.

Everything the dashboard renders is an aggregate over `workflow_runs`,
`projects`, `users` and `feedback` for a rolling window. Counts are paired with
the immediately preceding window of the same length so the UI can show a delta
without a second request.
"""

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from lib.models.user import UserRole


class ActivityGranularity(str, Enum):
    """Bucket size of the activity series."""

    DAY = "day"
    WEEK = "week"


class MetricWithDelta(BaseModel):
    """A count for the selected window alongside the preceding one."""

    current: int = Field(description="Count within the selected window")
    previous: int = Field(
        description="Count within the window of equal length that preceded it"
    )


class ActivityPoint(BaseModel):
    """One bucket of the activity series."""

    bucket: date = Field(description="Start of the day/week bucket (UTC)")
    workflow_runs: int
    active_users: int
    projects_created: int


class WorkflowStatusCounts(BaseModel):
    """Run outcomes for a workflow type within the window.

    Every field is required: the query always produces all six, and an
    optional count would reach the client as `number | undefined`.
    """

    completed: int
    failed: int
    cancelled: int
    running: int
    pending: int
    awaiting_approval: int


class WorkflowUsageItem(BaseModel):
    """Usage of a single workflow type within the window."""

    type: str = Field(
        description=(
            "Workflow type slug as persisted. Retired workflows keep their old "
            "slug and no longer resolve to a manifest."
        )
    )
    name: str = Field(description="Display name from the manifest, or the slug")
    is_internal: bool = Field(
        description="Internal workflows run as dependencies, not user selections"
    )
    is_retired: bool = Field(description="No manifest is registered for this slug")
    runs: int
    statuses: WorkflowStatusCounts
    median_duration_seconds: float | None = Field(
        description="Median wall-clock duration of COMPLETED runs, if any completed"
    )
    thumbs_up: int
    thumbs_down: int


class ActiveUserItem(BaseModel):
    """A user's activity within the window."""

    user_id: uuid.UUID
    name: str
    email: str
    role: UserRole
    workflow_runs: int
    projects: int = Field(description="Distinct projects the user ran assessments on")
    last_active_at: datetime


class DashboardFeedbackSummary(BaseModel):
    """Aggregate feedback signal for the window.

    Counts only — feedback text and its authors stay behind the per-project
    visibility rules enforced by the feedback listing endpoint.
    """

    thumbs_up: int
    thumbs_down: int
    with_comment: int = Field(description="Feedback entries that carry written text")


class AdminDashboardResponse(BaseModel):
    """Everything the admin usage dashboard renders."""

    period_days: int
    period_start: datetime
    period_end: datetime
    granularity: ActivityGranularity
    cache_ttl_seconds: int = Field(
        description=(
            "How long these figures may be served before being recomputed. "
            "`period_end` is the moment they were computed, so the two together "
            "tell the reader how stale what they are looking at can be."
        )
    )

    total_users: int = Field(description="All-time registered users")
    active_users: MetricWithDelta
    new_users: MetricWithDelta
    projects_created: MetricWithDelta
    assessments_run: MetricWithDelta
    feedback_received: MetricWithDelta

    activity: list[ActivityPoint]
    workflows: list[WorkflowUsageItem]
    top_users: list[ActiveUserItem]
    feedback: DashboardFeedbackSummary
