"""Aggregation queries behind the admin usage dashboard.

Each function owns one aggregate and takes a session from its caller, which
runs them one after another on a single connection — see the service for why
this deliberately does not fan out. Counts for the selected window and the
preceding one are produced by a single query using conditional aggregation.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col

from lib.models.feedback import Feedback, FeedbackType
from lib.models.project import FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.admin_dashboard.models import (
    ActiveUserItem,
    ActivityPoint,
    DashboardFeedbackSummary,
    ActivityGranularity,
    MetricWithDelta,
    WorkflowStatusCounts,
    WorkflowUsageItem,
)
from lib.services.admin_dashboard.window import DashboardWindow
from lib.workflows.registry import get_all_manifests

# Median ≈ the typical run; a mean would be dragged around by the odd very slow
# one. Same choice as the pre-run duration estimates.
_DURATION_PERCENTILE = 0.5


def _assessment_type_values() -> list[str]:
    """Slugs of the workflows a user can choose to run today.

    An allowlist rather than "everything that is not internal": rows outlive
    the workflows that wrote them, and a retired slug carries no manifest to
    say which kind it was. Most retired slugs are old pipeline steps
    (chunk_splitting, citation_detection, …), so admitting them would report
    machine work as user activity — by an order of magnitude on older windows.
    They are still counted in the per-workflow table, flagged as retired.
    """
    return [
        workflow_type.value
        for workflow_type, manifest in get_all_manifests().items()
        if not manifest.is_internal
    ]


def _is_assessment() -> ColumnElement[bool]:
    """Restrict to workflows a user actually chose to run."""
    return col(WorkflowRun.type).in_(_assessment_type_values())


def _in_current(window: DashboardWindow, ts: Mapped[datetime]) -> ColumnElement[bool]:
    """The selected window, upper bound included.

    The bound is not decoration: without it a row written while the aggregates
    are running lands in some of them and not others, and the payload can carry
    counts for rows newer than the `period_end` it advertises.
    """
    return and_(ts >= window.start, ts < window.end)


def _in_previous(window: DashboardWindow, ts: Mapped[datetime]) -> ColumnElement[bool]:
    return and_(ts >= window.previous_start, ts < window.start)


def _is_shared_feedback() -> ColumnElement[bool]:
    """Only feedback whose author allowed it to be shared with admins.

    The two sharing levels do not grant the same thing, so neither does this:

    - `FULL_PROJECT` — "Administrators will be able to view the project, all
      uploaded files, and all analysis results." Broad consent; every feedback
      row on the project counts.
    - `ISSUE_ONLY` — "Share only this issue information." Feedback that hangs
      off an issue counts; feedback on a chunk or a claim (`issue_id IS NULL`)
      does not, and the listing endpoint drops those rows too, through its
      `Issue` join.
    - `PRIVATE`, the dialog's default — "Don't share any information / Your
      feedback is visible only to you." Nothing counts, sentiment and
      has-a-comment included.

    Written as an allowlist of what each level grants rather than "not
    private", so a visibility level added later is excluded until someone
    decides what it shares.

    Requires the caller to have joined Feedback -> WorkflowRun -> Project.
    """
    visibility = col(Project.feedback_visibility)
    return or_(
        visibility == FeedbackVisibility.FULL_PROJECT,
        and_(
            visibility == FeedbackVisibility.ISSUE_ONLY,
            col(Feedback.issue_id).is_not(None),
        ),
    )


def _current_and_previous_counts(
    window: DashboardWindow, ts: Mapped[datetime]
) -> tuple[ColumnElement[int], ColumnElement[int]]:
    """Counts for both windows, for a query filtered to `previous_start` onward."""
    return (
        func.count(case((_in_current(window, ts), 1))),
        func.count(case((_in_previous(window, ts), 1))),
    )


async def get_user_metrics(
    session: AsyncSession, window: DashboardWindow
) -> tuple[int, MetricWithDelta]:
    """All-time user count, plus sign-ups in this window and the previous one."""
    created_at = col(User.created_at)
    current, previous = _current_and_previous_counts(window, created_at)
    row = (await session.execute(select(func.count(), current, previous))).one()
    return row[0], MetricWithDelta(current=row[1], previous=row[2])


async def get_project_metrics(
    session: AsyncSession, window: DashboardWindow
) -> MetricWithDelta:
    """Projects created in this window and the previous one."""
    created_at = col(Project.created_at)
    current, previous = _current_and_previous_counts(window, created_at)
    stmt = select(current, previous).where(created_at >= window.previous_start)
    row = (await session.execute(stmt)).one()
    return MetricWithDelta(current=row[0], previous=row[1])


async def get_assessment_metrics(
    session: AsyncSession, window: DashboardWindow
) -> MetricWithDelta:
    """Assessment runs started in this window and the previous one."""
    created_at = col(WorkflowRun.created_at)
    current, previous = _current_and_previous_counts(window, created_at)
    stmt = select(current, previous).where(
        created_at >= window.previous_start, _is_assessment()
    )
    row = (await session.execute(stmt)).one()
    return MetricWithDelta(current=row[0], previous=row[1])


async def get_active_user_metrics(
    session: AsyncSession, window: DashboardWindow
) -> MetricWithDelta:
    """Distinct users who ran an assessment, per window.

    Attribution goes through the project owner: a run has no user of its own.
    """
    created_at = col(WorkflowRun.created_at)
    user_id = col(Project.user_id)
    stmt = (
        select(
            func.count(distinct(case((_in_current(window, created_at), user_id)))),
            func.count(distinct(case((_in_previous(window, created_at), user_id)))),
        )
        .select_from(WorkflowRun)
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .where(created_at >= window.previous_start, _is_assessment())
    )
    row = (await session.execute(stmt)).one()
    return MetricWithDelta(current=row[0], previous=row[1])


async def get_feedback_metrics(
    session: AsyncSession, window: DashboardWindow
) -> tuple[MetricWithDelta, DashboardFeedbackSummary]:
    """Feedback volume per window, and the thumbs split for the current one.

    Counts only, and only over feedback its author agreed to share — see
    `_is_shared_feedback`. Text and authorship never leave the listing
    endpoint.
    """
    created_at = col(Feedback.created_at)
    feedback_type = col(Feedback.feedback_type)
    feedback_text = col(Feedback.feedback_text)
    current, previous = _current_and_previous_counts(window, created_at)
    in_current = _in_current(window, created_at)

    stmt = select(
        current,
        previous,
        func.count(
            case((and_(in_current, feedback_type == FeedbackType.THUMBS_UP), 1))
        ),
        func.count(
            case((and_(in_current, feedback_type == FeedbackType.THUMBS_DOWN), 1))
        ),
        func.count(
            case(
                (
                    and_(
                        in_current,
                        feedback_text.is_not(None),
                        func.trim(feedback_text) != "",
                    ),
                    1,
                )
            )
        ),
    )
    stmt = (
        stmt.select_from(Feedback)
        .join(WorkflowRun, col(Feedback.workflow_run_id) == col(WorkflowRun.id))
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .where(created_at >= window.previous_start, _is_shared_feedback())
    )

    row = (await session.execute(stmt)).one()
    return (
        MetricWithDelta(current=row[0], previous=row[1]),
        DashboardFeedbackSummary(
            thumbs_up=row[2], thumbs_down=row[3], with_comment=row[4]
        ),
    )


def _bucket_starts(window: DashboardWindow) -> list[date]:
    """Every bucket in the window, so the series has no holes.

    Mirrors `date_trunc`: days start at midnight UTC, weeks on Monday (both
    Postgres' and `weekday()`'s convention).
    """
    step = timedelta(days=7 if window.granularity == ActivityGranularity.WEEK else 1)
    first = window.start.date()
    if window.granularity == ActivityGranularity.WEEK:
        first -= timedelta(days=first.weekday())

    buckets: list[date] = []
    cursor = first
    last = window.end.date()
    while cursor <= last:
        buckets.append(cursor)
        cursor += step
    return buckets


async def get_activity(
    session: AsyncSession, window: DashboardWindow
) -> list[ActivityPoint]:
    """Assessment runs, distinct active users, and new projects per bucket."""
    unit = window.granularity.value

    # date_trunc on a timestamptz truncates in the session's TimeZone, which
    # nothing here sets. Converting to UTC first makes the bucket keys match
    # the UTC dates `_bucket_starts` generates whatever the database is set to;
    # otherwise a non-UTC server shifts rows into a key the dense series has no
    # slot for, and their counts silently vanish.
    run_bucket = func.date_trunc(
        unit, func.timezone("UTC", col(WorkflowRun.created_at))
    )
    runs_stmt = (
        select(
            run_bucket.label("bucket"),
            func.count().label("runs"),
            func.count(distinct(col(Project.user_id))).label("users"),
        )
        .select_from(WorkflowRun)
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .where(_in_current(window, col(WorkflowRun.created_at)), _is_assessment())
        .group_by(run_bucket)
    )

    project_bucket = func.date_trunc(
        unit, func.timezone("UTC", col(Project.created_at))
    )
    projects_stmt = (
        select(project_bucket.label("bucket"), func.count().label("projects"))
        .where(_in_current(window, col(Project.created_at)))
        .group_by(project_bucket)
    )

    run_rows = (await session.execute(runs_stmt)).all()
    project_rows = (await session.execute(projects_stmt)).all()

    runs_by_bucket = {row[0].date(): (row[1], row[2]) for row in run_rows}
    projects_by_bucket = {row[0].date(): row[1] for row in project_rows}

    return [
        ActivityPoint(
            bucket=bucket,
            workflow_runs=runs_by_bucket.get(bucket, (0, 0))[0],
            active_users=runs_by_bucket.get(bucket, (0, 0))[1],
            projects_created=projects_by_bucket.get(bucket, 0),
        )
        for bucket in _bucket_starts(window)
    ]


async def _get_feedback_by_workflow_type(
    session: AsyncSession, window: DashboardWindow
) -> dict[str, tuple[int, int]]:
    """Thumbs up/down per workflow type, keyed by the run's type slug.

    Shared feedback only, for the same reason the totals are — a per-workflow
    breakdown of private feedback discloses it just as surely.
    """
    feedback_type = col(Feedback.feedback_type)
    stmt = (
        select(
            col(WorkflowRun.type),
            func.count(case((feedback_type == FeedbackType.THUMBS_UP, 1))),
            func.count(case((feedback_type == FeedbackType.THUMBS_DOWN, 1))),
        )
        .select_from(Feedback)
        .join(WorkflowRun, col(Feedback.workflow_run_id) == col(WorkflowRun.id))
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .where(_in_current(window, col(Feedback.created_at)), _is_shared_feedback())
        .group_by(col(WorkflowRun.type))
    )
    rows = (await session.execute(stmt)).all()
    return {str(row[0]): (row[1], row[2]) for row in rows}


async def get_workflow_usage(
    session: AsyncSession, window: DashboardWindow
) -> list[WorkflowUsageItem]:
    """Per workflow type: run count, outcome split, median duration, feedback."""
    status = col(WorkflowRun.status)
    duration_seconds = func.extract(
        "epoch", col(WorkflowRun.completed_at)
    ) - func.extract("epoch", col(WorkflowRun.started_at))

    stmt = (
        select(
            col(WorkflowRun.type).label("type"),
            func.count().label("runs"),
            func.count(case((status == WorkflowRunStatus.COMPLETED, 1))),
            func.count(case((status == WorkflowRunStatus.FAILED, 1))),
            func.count(case((status == WorkflowRunStatus.CANCELLED, 1))),
            func.count(case((status == WorkflowRunStatus.RUNNING, 1))),
            func.count(case((status == WorkflowRunStatus.PENDING, 1))),
            func.count(case((status == WorkflowRunStatus.AWAITING_APPROVAL, 1))),
            func.percentile_cont(_DURATION_PERCENTILE)
            .within_group(duration_seconds.asc())
            .filter(
                and_(
                    status == WorkflowRunStatus.COMPLETED,
                    col(WorkflowRun.started_at).is_not(None),
                    col(WorkflowRun.completed_at).is_not(None),
                )
            )
            .label("median_duration"),
        )
        .where(_in_current(window, col(WorkflowRun.created_at)))
        .group_by(col(WorkflowRun.type))
        .order_by(func.count().desc())
    )

    rows = (await session.execute(stmt)).all()
    feedback_by_type = await _get_feedback_by_workflow_type(session, window)
    manifests = {
        workflow_type.value: manifest
        for workflow_type, manifest in get_all_manifests().items()
    }

    items: list[WorkflowUsageItem] = []
    for row in rows:
        slug = str(row[0])
        manifest = manifests.get(slug)
        thumbs_up, thumbs_down = feedback_by_type.get(slug, (0, 0))
        items.append(
            WorkflowUsageItem(
                type=slug,
                name=manifest.name if manifest else slug.replace("_", " ").title(),
                is_internal=manifest.is_internal if manifest else False,
                is_retired=manifest is None,
                runs=row[1],
                statuses=WorkflowStatusCounts(
                    completed=row[2],
                    failed=row[3],
                    cancelled=row[4],
                    running=row[5],
                    pending=row[6],
                    awaiting_approval=row[7],
                ),
                median_duration_seconds=(float(row[8]) if row[8] is not None else None),
                thumbs_up=thumbs_up,
                thumbs_down=thumbs_down,
            )
        )
    return items


async def get_top_users(
    session: AsyncSession, window: DashboardWindow, limit: int
) -> list[ActiveUserItem]:
    """The busiest users in the window, by assessment runs."""
    run_count = func.count().label("runs")
    stmt = (
        select(
            col(User.id),
            col(User.name),
            col(User.email),
            col(User.role),
            run_count,
            func.count(distinct(col(Project.id))).label("projects"),
            func.max(col(WorkflowRun.created_at)).label("last_active_at"),
        )
        .select_from(WorkflowRun)
        .join(Project, col(WorkflowRun.project_id) == col(Project.id))
        .join(User, col(Project.user_id) == col(User.id))
        .where(_in_current(window, col(WorkflowRun.created_at)), _is_assessment())
        .group_by(col(User.id), col(User.name), col(User.email), col(User.role))
        .order_by(run_count.desc())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    return [
        ActiveUserItem(
            user_id=row[0],
            name=row[1],
            email=row[2],
            role=UserRole(row[3]),
            workflow_runs=row[4],
            projects=row[5],
            last_active_at=row[6],
        )
        for row in rows
    ]
