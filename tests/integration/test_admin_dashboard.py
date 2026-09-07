"""Integration tests for the admin usage dashboard aggregates.

Runs against the real database. Isolation comes from the fixture's own user and
from a workflow type slug that exists nowhere else, so the per-workflow and
per-user assertions are exact even though the aggregates are global. The
window-wide totals are asserted as lower bounds around the fixture's rows.

The fixture deliberately inserts both a retired slug (no manifest) and a live
assessment slug: the two are counted differently, and that difference is the
thing most likely to break.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue, IssueStatus
from lib.models.project import FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.admin_dashboard import ignored_users, queries, service
from lib.services.admin_dashboard.service import (
    CACHE_TTL_SECONDS,
    get_admin_dashboard,
)
from lib.services.admin_dashboard.window import DashboardWindow
from lib.workflows.models import SeverityEnum, WorkflowRunType

NOW = datetime.now(timezone.utc)

# A live, user-selectable workflow: these are what the assessment metrics count.
ASSESSMENT_SLUG = WorkflowRunType.FIGURES_TABLES_CHECK.value


class _Fixture:
    """Everything the fixture inserted, plus the slug that isolates it."""

    def __init__(
        self,
        user: User,
        project: Project,
        private_project: Project,
        issue_only_project: Project,
        slug: str,
    ):
        self.user = user
        self.project = project
        self.private_project = private_project
        self.issue_only_project = issue_only_project
        self.slug = slug


def _run(
    project_id: uuid.UUID,
    slug: str,
    status: WorkflowRunStatus,
    created_at: datetime,
    duration_seconds: float | None = None,
) -> WorkflowRun:
    started_at = created_at if duration_seconds is not None else None
    completed_at = (
        created_at + timedelta(seconds=duration_seconds)
        if duration_seconds is not None
        else None
    )
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=project_id,
        type=slug,  # type: ignore[arg-type]  # a retired slug: the column is a plain string
        langgraph_thread_id=str(uuid.uuid4()),
        status=status,
        created_at=created_at,
        last_updated_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
    )


@pytest_asyncio.fixture
async def dashboard_data():
    """A user with runs of both a retired and a live workflow type, and feedback.

    Four retired-slug runs sit inside a one-day window plus one ten days back,
    and three live-assessment runs sit inside it.
    """
    tag = str(uuid.uuid4()).replace("-", "")[:12]
    slug = f"dashboard_test_{tag}"

    user = User(
        id=uuid.uuid4(),
        email=f"dash-{tag}@example.com",
        name=f"Dash {tag}",
        role=UserRole.USER,
        show_experimental_features=False,
        created_at=NOW - timedelta(hours=1),
        last_updated_at=NOW - timedelta(hours=1),
    )
    project = Project(
        id=uuid.uuid4(),
        title=f"Dashboard project {tag}",
        user_id=user.id,
        created_at=NOW - timedelta(hours=1),
        last_updated_at=NOW - timedelta(hours=1),
        feedback_visibility=FeedbackVisibility.FULL_PROJECT,
    )
    # "Share only this issue information": issue feedback is shared, feedback
    # on a chunk or a claim is not.
    issue_only_project = Project(
        id=uuid.uuid4(),
        title=f"Issue-only project {tag}",
        user_id=user.id,
        created_at=NOW - timedelta(hours=1),
        last_updated_at=NOW - timedelta(hours=1),
        feedback_visibility=FeedbackVisibility.ISSUE_ONLY,
    )
    # The dialog's default: "Don't share any information."
    private_project = Project(
        id=uuid.uuid4(),
        title=f"Private project {tag}",
        user_id=user.id,
        created_at=NOW - timedelta(hours=1),
        last_updated_at=NOW - timedelta(hours=1),
        feedback_visibility=FeedbackVisibility.PRIVATE,
    )
    runs = [
        _run(
            project.id, slug, WorkflowRunStatus.COMPLETED, NOW - timedelta(hours=3), 10
        ),
        _run(
            project.id, slug, WorkflowRunStatus.COMPLETED, NOW - timedelta(hours=2), 30
        ),
        _run(project.id, slug, WorkflowRunStatus.FAILED, NOW - timedelta(hours=1)),
        _run(project.id, slug, WorkflowRunStatus.RUNNING, NOW - timedelta(minutes=30)),
        # Outside a one-day window: must not be counted.
        _run(
            project.id, slug, WorkflowRunStatus.COMPLETED, NOW - timedelta(days=10), 99
        ),
        # A live assessment type — the only runs here the assessment metrics count.
        _run(
            project.id,
            ASSESSMENT_SLUG,
            WorkflowRunStatus.COMPLETED,
            NOW - timedelta(hours=2),
            5,
        ),
        _run(
            project.id,
            ASSESSMENT_SLUG,
            WorkflowRunStatus.COMPLETED,
            NOW - timedelta(hours=1),
            7,
        ),
        _run(
            project.id,
            ASSESSMENT_SLUG,
            WorkflowRunStatus.FAILED,
            NOW - timedelta(minutes=45),
        ),
        # Newer than any window's end: nothing may count it. On the isolated
        # slug so the per-workflow count below can prove it.
        _run(
            project.id, slug, WorkflowRunStatus.COMPLETED, NOW + timedelta(hours=6), 5
        ),
        # 01:30 UTC two days back: under a UTC-3 session this falls on the day
        # before, which is what makes the bucketing test able to fail. Two days
        # rather than one so it is outside a one-day window whatever time of
        # day the suite runs — at 00:30 UTC, "yesterday at 01:30" is 23 hours
        # ago, and the exact counts below would pick it up.
        _run(
            project.id,
            ASSESSMENT_SLUG,
            WorkflowRunStatus.COMPLETED,
            (NOW - timedelta(days=2)).replace(
                hour=1, minute=30, second=0, microsecond=0
            ),
            5,
        ),
        # Carries the private project's feedback. On the isolated slug so the
        # per-workflow feedback count is exactly this fixture's rows.
        _run(
            private_project.id,
            slug,
            WorkflowRunStatus.COMPLETED,
            NOW - timedelta(hours=2),
            5,
        ),
        # Carries the issue-only project's two feedback rows. Ten seconds, the
        # same as an existing run, so the median duration does not move.
        _run(
            issue_only_project.id,
            slug,
            WorkflowRunStatus.COMPLETED,
            NOW - timedelta(hours=2),
            10,
        ),
    ]
    issue = Issue(
        id=uuid.uuid4(),
        project_id=issue_only_project.id,
        workflow_run_id=runs[-1].id,
        issue_hash=f"hash-{tag}",
        title=f"Issue {tag}",
        description="Something to leave feedback on",
        severity=SeverityEnum.LOW,
        workflow_type=WorkflowRunType.FIGURES_TABLES_CHECK,
        status=IssueStatus.ACTIVE,
        revision=1,
        created_at=NOW - timedelta(minutes=30),
    )
    feedbacks = [
        Feedback(
            id=uuid.uuid4(),
            workflow_run_id=runs[0].id,
            user_id=user.id,
            entity_path={},
            feedback_type=FeedbackType.THUMBS_UP,
            created_at=NOW - timedelta(minutes=20),
            updated_at=NOW - timedelta(minutes=20),
        ),
        Feedback(
            id=uuid.uuid4(),
            workflow_run_id=runs[1].id,
            user_id=user.id,
            entity_path={},
            feedback_type=FeedbackType.THUMBS_DOWN,
            feedback_text="Missed a citation",
            created_at=NOW - timedelta(minutes=10),
            updated_at=NOW - timedelta(minutes=10),
        ),
        # On the private project: must not reach any aggregate, not even as a
        # count or as "one of these has a written comment".
        Feedback(
            id=uuid.uuid4(),
            workflow_run_id=runs[-2].id,
            user_id=user.id,
            entity_path={},
            feedback_type=FeedbackType.THUMBS_DOWN,
            feedback_text="Private, and not for admin eyes",
            created_at=NOW - timedelta(minutes=5),
            updated_at=NOW - timedelta(minutes=5),
        ),
        # Issue-only project, attached to an issue: shared, so counted.
        Feedback(
            id=uuid.uuid4(),
            workflow_run_id=runs[-1].id,
            user_id=user.id,
            issue_id=issue.id,
            entity_path={},
            feedback_type=FeedbackType.THUMBS_UP,
            created_at=NOW - timedelta(minutes=4),
            updated_at=NOW - timedelta(minutes=4),
        ),
        # Issue-only project, on a chunk: "only this issue information" does
        # not cover it, and the listing endpoint drops it too.
        Feedback(
            id=uuid.uuid4(),
            workflow_run_id=runs[-1].id,
            user_id=user.id,
            entity_path={"chunk_index": 2},
            feedback_type=FeedbackType.THUMBS_DOWN,
            feedback_text="Not covered by issue-only sharing",
            created_at=NOW - timedelta(minutes=3),
            updated_at=NOW - timedelta(minutes=3),
        ),
    ]

    # Committed in FK order: nothing declares a relationship() between these
    # models, so the unit of work has no dependency graph to sort inserts by.
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
        session.add(project)
        session.add(private_project)
        session.add(issue_only_project)
        await session.commit()
        for run in runs:
            session.add(run)
        await session.commit()
        session.add(issue)
        await session.commit()
        for feedback in feedbacks:
            session.add(feedback)
        await session.commit()

    yield _Fixture(user, project, private_project, issue_only_project, slug)

    async with get_async_db_session() as session:
        for model, ids in (
            (Feedback, [f.id for f in feedbacks]),
            (Issue, [issue.id]),
            (WorkflowRun, [r.id for r in runs]),
            (Project, [project.id, private_project.id, issue_only_project.id]),
            (User, [user.id]),
        ):
            for row_id in ids:
                found = (
                    await session.execute(select(model).where(col(model.id) == row_id))
                ).scalar_one_or_none()
                if found is not None:
                    await session.delete(found)
        await session.commit()


@pytest.mark.asyncio
async def test_workflow_usage_reports_outcomes_and_median_duration(dashboard_data):
    response = await get_admin_dashboard(days=1)

    item = next(w for w in response.workflows if w.type == dashboard_data.slug)

    # Eight runs carry this slug: six inside the window (one each on the
    # private and issue-only projects), one ten days back, and one six hours
    # ahead. Both bounds of the window are load-bearing here.
    assert item.runs == 6
    assert item.statuses.completed == 4
    assert item.statuses.failed == 1
    assert item.statuses.running == 1
    # Completed durations inside the window are 5, 10, 10 and 30 seconds.
    assert item.median_duration_seconds == pytest.approx(10.0)
    assert item.is_retired is True
    assert item.is_internal is False
    assert item.name == dashboard_data.slug.replace("_", " ").title()


@pytest.mark.asyncio
async def test_workflow_usage_attributes_feedback_to_the_run_type(dashboard_data):
    response = await get_admin_dashboard(days=1)

    item = next(w for w in response.workflows if w.type == dashboard_data.slug)

    # Shared: one up on the full-project one, one up on the issue-only one's
    # issue. Excluded: the private project's down, and the issue-only
    # project's chunk-level down.
    assert item.thumbs_up == 2
    assert item.thumbs_down == 1


@pytest.mark.asyncio
async def test_top_users_counts_only_live_assessment_runs(dashboard_data):
    """Retired-slug runs are not the user's work; future-dated ones are not yet."""
    window = DashboardWindow.for_days(1)

    async with get_async_db_session() as session:
        rows = await queries.get_top_users(session, window, limit=1000)

    row = next(r for r in rows if r.user_id == dashboard_data.user.id)

    assert row.workflow_runs == 3
    assert row.projects == 1
    assert row.email == dashboard_data.user.email
    assert row.last_active_at < window.end


@pytest.mark.asyncio
async def test_activity_series_is_dense_and_covers_the_window(dashboard_data):
    response = await get_admin_dashboard(days=7)

    buckets = [point.bucket for point in response.activity]

    assert len(buckets) == len(set(buckets))
    assert buckets == sorted(buckets)
    assert buckets[-1] == response.period_end.date()
    assert sum(point.workflow_runs for point in response.activity) >= 3


@pytest.mark.asyncio
async def test_fixture_rows_move_the_totals(dashboard_data):
    response = await get_admin_dashboard(days=1)

    assert response.active_users.current >= 1
    assert response.new_users.current >= 1
    assert response.projects_created.current >= 1
    assert response.assessments_run.current >= 3
    assert response.feedback_received.current >= 2
    assert response.feedback.thumbs_up >= 1
    assert response.feedback.thumbs_down >= 1
    assert response.feedback.with_comment >= 1
    assert response.total_users >= 1
    assert response.period_days == 1


@pytest.mark.asyncio
async def test_response_advertises_the_real_cache_window(dashboard_data):
    """The page prints this number to the reader, so it cannot be a guess."""
    response = await get_admin_dashboard(days=1)

    assert response.cache_ttl_seconds == CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_only_one_computation_runs_at_a_time(dashboard_data, monkeypatch):
    """The guard that keeps this page from slowing the rest of the app down.

    Each computation holds one connection from a pool of 8 (+3 overflow) that
    every other request shares, so concurrent callers have to queue rather than
    compete. Without the semaphore in the service, 25 concurrent requests took
    an ordinary /api/projects call from 24 ms to 780 ms.
    """
    # A semaphore binds to the loop that first awaits it, and pytest-asyncio
    # gives each test its own loop. Sharing the module-level one across the two
    # tests that touch it raises "bound to a different event loop" for whichever
    # runs second — masked today only because xdist usually puts them in
    # different processes. A fresh slot per test keeps the property under test
    # (the service serialises through whatever is in that attribute) without
    # the cross-loop coupling.
    monkeypatch.setattr(service, "_COMPUTATION_SLOT", asyncio.Semaphore(1))

    in_flight = 0
    peak = 0
    real_get_user_metrics = queries.get_user_metrics

    async def counting_get_user_metrics(session, window, ignored_user_ids=()):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            # An await point inside the guarded section: if two computations
            # could overlap, this is where they would.
            await asyncio.sleep(0.02)
            return await real_get_user_metrics(session, window, ignored_user_ids)
        finally:
            in_flight -= 1

    monkeypatch.setattr(queries, "get_user_metrics", counting_get_user_metrics)

    responses = await asyncio.gather(*[get_admin_dashboard(days=1) for _ in range(6)])

    assert peak == 1
    assert len(responses) == 6
    assert all(response.period_days == 1 for response in responses)


@pytest.mark.asyncio
async def test_private_feedback_stays_out_of_every_aggregate(dashboard_data):
    """ "Don't share any information" has to mean the counts too.

    The fixture leaves three feedback rows on its isolated workflow slug: a
    thumbs-up and a thumbs-down on the shared project, and a thumbs-down with
    text on the PRIVATE one. An aggregate discloses that private row just as
    surely as a listing would, only less legibly.

    The per-workflow counts are exact because the slug exists nowhere else. The
    window totals are global, so they are measured either side of flipping the
    private project inside a single snapshot — the flip is never committed, and
    REPEATABLE READ keeps a parallel worker's inserts from moving the numbers
    between the two reads.
    """
    window = DashboardWindow.for_days(1)

    async with get_async_db_session() as session:
        by_type = await queries._get_feedback_by_workflow_type(session, window)
        assert by_type[dashboard_data.slug] == (2, 1)

    async with get_async_db_session() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        before_volume, before_summary = await queries.get_feedback_metrics(
            session, window
        )

        await session.execute(
            update(Project)
            .where(col(Project.id) == dashboard_data.private_project.id)
            .values(feedback_visibility=FeedbackVisibility.FULL_PROJECT)
        )

        after_volume, after_summary = await queries.get_feedback_metrics(
            session, window
        )
        after_by_type = await queries._get_feedback_by_workflow_type(session, window)
        await session.rollback()

    assert after_volume.current == before_volume.current + 1
    assert after_summary.thumbs_down == before_summary.thumbs_down + 1
    assert after_summary.with_comment == before_summary.with_comment + 1
    assert after_summary.thumbs_up == before_summary.thumbs_up
    assert after_by_type[dashboard_data.slug] == (2, 2)


@pytest.mark.asyncio
async def test_buckets_do_not_move_with_the_database_timezone(dashboard_data):
    """`date_trunc` must bucket in UTC, not in the session's TimeZone.

    The dense series is built from UTC dates, so a server truncating in local
    time keys rows to a slot that does not exist and drops their counts
    silently. The fixture's 01:30 UTC run is what a UTC-3 session would move to
    the previous day.

    Both measurements share one REPEATABLE READ snapshot: the suite runs in
    parallel, and under READ COMMITTED another worker's insert between the two
    calls would fail this for the wrong reason.
    """
    window = DashboardWindow.for_days(7)

    async with get_async_db_session() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        in_utc = await queries.get_activity(session, window)
        await session.execute(text("SET LOCAL TIME ZONE 'America/Sao_Paulo'"))
        shifted = await queries.get_activity(session, window)

    assert shifted == in_utc


@pytest.mark.asyncio
async def test_the_transaction_carries_a_snapshot_and_a_timeout(
    dashboard_data, monkeypatch
):
    """Both settings are load-bearing and both fail silently if removed.

    Drop the isolation level and the aggregates go back to seeing eight
    different moments; drop the timeout and a pathological plan pins the
    connection every queued caller is waiting for. Neither loss breaks a test
    that only checks numbers, so this one reads the settings off the session the
    service actually opened.
    """
    observed: dict[str, str] = {}
    real_get_user_metrics = queries.get_user_metrics

    async def peeking_get_user_metrics(session, window, ignored_user_ids=()):
        observed["isolation"] = (
            await session.execute(text("SHOW transaction_isolation"))
        ).scalar_one()
        observed["timeout"] = (
            await session.execute(text("SHOW statement_timeout"))
        ).scalar_one()
        return await real_get_user_metrics(session, window, ignored_user_ids)

    monkeypatch.setattr(queries, "get_user_metrics", peeking_get_user_metrics)

    await get_admin_dashboard(days=1)

    assert observed["isolation"] == "repeatable read"
    assert observed["timeout"] == "15s"


@pytest.mark.asyncio
async def test_issue_only_sharing_covers_the_issue_and_nothing_else(dashboard_data):
    """ "Share only this issue information" is narrower than "share".

    The fixture leaves two rows on an ISSUE_ONLY project: a thumbs-up attached
    to an issue, and a thumbs-down on a chunk. Only the first is what the author
    agreed to share, and it is the only one the listing endpoint would return.
    """
    window = DashboardWindow.for_days(1)

    async with get_async_db_session() as session:
        shared = (
            await session.execute(
                select(Feedback.id)
                .join(WorkflowRun, col(Feedback.workflow_run_id) == col(WorkflowRun.id))
                .join(Project, col(WorkflowRun.project_id) == col(Project.id))
                .where(
                    col(WorkflowRun.project_id) == dashboard_data.issue_only_project.id,
                    queries._is_shared_feedback(),
                )
            )
        ).scalars()
        shared_ids = list(shared)

        issue_feedback = (
            await session.execute(
                select(Feedback.id).where(col(Feedback.issue_id).is_not(None))
            )
        ).scalars()
        issue_feedback_ids = set(issue_feedback)

    assert len(shared_ids) == 1
    assert shared_ids[0] in issue_feedback_ids

    # And the chunk-level row moves no count: the up/down split for this slug
    # holds at two shared ups and one shared down.
    async with get_async_db_session() as session:
        by_type = await queries._get_feedback_by_workflow_type(session, window)

    assert by_type[dashboard_data.slug] == (2, 1)


@pytest.mark.asyncio
async def test_period_end_is_when_the_figures_were_computed(
    dashboard_data, monkeypatch
):
    """Not when the request arrived, which is what the page would misreport.

    Requests queue behind the computation slot, so a caller that waited its
    turn would otherwise print an "as of" from before the wait — and its window
    would end there too, silently excluding anything that happened during it.
    """
    slot = asyncio.Semaphore(1)  # this test's own loop; see the note above
    monkeypatch.setattr(service, "_COMPUTATION_SLOT", slot)

    async with slot:
        queued = asyncio.create_task(get_admin_dashboard(days=1))
        await asyncio.sleep(0.3)  # long enough for the task to reach the slot
        released_at = datetime.now(timezone.utc)

    response = await queued

    assert response.period_end >= released_at


@pytest.mark.asyncio
async def test_ignoring_a_user_removes_their_rows_from_every_aggregate(dashboard_data):
    """The eval account's runs must not read as adoption.

    The fixture's user is the one ignored, so what disappears is known exactly:
    one sign-up, three projects, three assessment runs, one active user, and
    the three shared feedback rows (two up, one down, one with text). The
    window totals are global, so each is measured with and without the ignore
    list inside one REPEATABLE READ snapshot — a parallel worker's inserts
    cannot move them between the two reads.
    """
    window = DashboardWindow.for_days(1)
    ignored = [dashboard_data.user.id]

    async with get_async_db_session() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        all_total, all_new = await queries.get_user_metrics(session, window)
        total, new = await queries.get_user_metrics(session, window, ignored)
        all_projects = await queries.get_project_metrics(session, window)
        projects = await queries.get_project_metrics(session, window, ignored)
        all_runs = await queries.get_assessment_metrics(session, window)
        runs = await queries.get_assessment_metrics(session, window, ignored)
        all_active = await queries.get_active_user_metrics(session, window)
        active = await queries.get_active_user_metrics(session, window, ignored)
        all_feedback, all_summary = await queries.get_feedback_metrics(session, window)
        feedback, summary = await queries.get_feedback_metrics(
            session, window, ignored
        )
        all_activity = await queries.get_activity(session, window)
        activity = await queries.get_activity(session, window, ignored)
        workflows = await queries.get_workflow_usage(session, window, ignored)
        top_users = await queries.get_top_users(session, window, 1000, ignored)

    assert all_total - total == 1
    assert all_new.current - new.current == 1
    assert all_projects.current - projects.current == 3
    assert all_runs.current - runs.current == 3
    assert all_active.current - active.current == 1
    assert all_feedback.current - feedback.current == 3
    assert all_summary.thumbs_up - summary.thumbs_up == 2
    assert all_summary.thumbs_down - summary.thumbs_down == 1
    assert all_summary.with_comment - summary.with_comment == 1

    def runs_in(points):
        return sum(point.workflow_runs for point in points)

    def projects_in(points):
        return sum(point.projects_created for point in points)

    assert runs_in(all_activity) - runs_in(activity) == 3
    assert projects_in(all_activity) - projects_in(activity) == 3
    assert all(item.type != dashboard_data.slug for item in workflows)
    assert all(row.user_id != dashboard_data.user.id for row in top_users)


@pytest.mark.asyncio
async def test_the_payload_says_who_it_left_out(dashboard_data):
    """Sorted and de-duplicated, so the UI's chips and the figures agree."""
    twice = [dashboard_data.user.id, dashboard_data.user.id]

    response = await get_admin_dashboard(days=1, ignored_user_ids=twice)

    assert response.ignored_user_ids == [dashboard_data.user.id]
    assert all(item.type != dashboard_data.slug for item in response.workflows)
    assert all(row.user_id != dashboard_data.user.id for row in response.top_users)


@pytest.mark.asyncio
async def test_nobody_ignored_leaves_every_figure_where_it_was(dashboard_data):
    """An empty ignore list is the plain aggregate, not a filter that matches nothing."""
    window = DashboardWindow.for_days(1)

    async with get_async_db_session() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        plain = await queries.get_assessment_metrics(session, window)
        explicit = await queries.get_assessment_metrics(session, window, [])
        plain_rows = await queries.get_top_users(session, window, 1000)
        explicit_rows = await queries.get_top_users(session, window, 1000, [])

    assert explicit == plain
    assert explicit_rows == plain_rows


@pytest.mark.asyncio
async def test_default_ignore_list_names_only_users_that_exist(
    dashboard_data, monkeypatch
):
    """The eval accounts are looked for, not assumed.

    Production has never run the evals and has no such user; the default there
    has to be nobody, not an error or an id that matches nothing. Checked with
    one email that exists (the fixture's user) and one that cannot.
    """
    monkeypatch.setattr(
        ignored_users,
        "DEFAULT_IGNORED_USER_EMAILS",
        (dashboard_data.user.email, f"nobody-{uuid.uuid4()}@example.com"),
    )

    found = await ignored_users.get_default_ignored_users()

    assert [user.user_id for user in found] == [dashboard_data.user.id]
    assert found[0].email == dashboard_data.user.email


@pytest.mark.asyncio
async def test_default_ignore_list_is_empty_when_no_eval_account_exists(monkeypatch):
    monkeypatch.setattr(
        ignored_users,
        "DEFAULT_IGNORED_USER_EMAILS",
        (f"nobody-{uuid.uuid4()}@example.com",),
    )

    assert await ignored_users.get_default_ignored_users() == []
