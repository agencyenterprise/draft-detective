"""Assembles the admin usage dashboard payload."""

import asyncio
import uuid
from collections.abc import Sequence

from sqlalchemy import text

from lib.config.database import get_async_db_session
from lib.services.admin_dashboard import queries
from lib.services.admin_dashboard.models import AdminDashboardResponse
from lib.services.admin_dashboard.window import DashboardWindow

# Enough rows to see who is driving usage without turning the card into the
# user-management table, which already exists at /users.
_TOP_USERS_LIMIT = 10

# One dashboard computation at a time per worker process.
#
# Every aggregate here is a sequential scan of `workflow_runs`, and one request
# holds its connection for the whole set (~200 ms against 100k runs). The engine
# pool is 8 connections plus 3 overflow, shared with every other request the
# worker serves, so unbounded concurrency on this endpoint is what would make
# the rest of the app crawl: measured at 25 concurrent requests, an ordinary
# /api/projects call went from 24 ms to 780 ms. The endpoint layer's TTL cache
# already collapses repeat loads of the same window; this bounds the remaining
# case — several distinct windows requested at once — to a single connection.
# Requests queue instead of competing, which is the right trade for a page a
# handful of admins open.
_COMPUTATION_SLOT = asyncio.Semaphore(1)

# How long the endpoint may serve a computed payload before recomputing. Lives
# here rather than in the router so the router's cache decorator and the
# `cache_ttl_seconds` the response advertises to the UI cannot drift apart: the
# page tells the reader this number, and it has to be the real one.
CACHE_TTL_SECONDS = 300

# A pathological plan (a much larger table, a bad statistics day) must not pin
# the connection indefinitely, since callers are queued behind it. Nothing here
# comes close: the widest window measures ~225 ms.
_STATEMENT_TIMEOUT_MS = 15_000


async def get_admin_dashboard(
    days: int, ignored_user_ids: Sequence[uuid.UUID] = ()
) -> AdminDashboardResponse:
    """Every dashboard aggregate for a rolling window of `days`.

    `ignored_user_ids` are left out of every figure — see the queries module
    for what that removes. The response echoes them sorted and de-duplicated,
    so the same selection always describes itself the same way.

    The aggregates are independent, but they share one session and run
    sequentially: they are all scans of the same few tables, and the async
    engine's pool is small enough that fanning one request across several
    connections is the wrong trade.

    Callers reaching the endpoint go through its TTL cache; this function
    always recomputes.
    """
    ignored = sorted(set(ignored_user_ids))

    async with _COMPUTATION_SLOT:
        # Inside the slot, not before it: `period_end` is what the page prints
        # as "as of", so it has to be the moment the figures were computed. A
        # request that waited its turn behind several others would otherwise
        # advertise the moment it joined the queue.
        window = DashboardWindow.for_days(days)

        async with get_async_db_session() as session:
            # One snapshot for all eight aggregates. Without it they run under
            # READ COMMITTED and each sees its own moment, so a run written
            # mid-request can be counted by the activity series but not by the
            # headline above it — the same quantity, disagreeing with itself on
            # one screen. Read-only REPEATABLE READ cannot raise a
            # serialization failure, so this costs nothing but the snapshot.
            # Must precede any query in the transaction.
            await session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            )

            # SET LOCAL scopes the timeout to this transaction, so it is undone
            # when the session's connection returns to the shared pool.
            await session.execute(
                text(f"SET LOCAL statement_timeout = {_STATEMENT_TIMEOUT_MS}")
            )

            total_users, new_users = await queries.get_user_metrics(
                session, window, ignored
            )
            projects_created = await queries.get_project_metrics(
                session, window, ignored
            )
            assessments_run = await queries.get_assessment_metrics(
                session, window, ignored
            )
            active_users = await queries.get_active_user_metrics(
                session, window, ignored
            )
            feedback_received, feedback = await queries.get_feedback_metrics(
                session, window, ignored
            )
            activity = await queries.get_activity(session, window, ignored)
            workflows = await queries.get_workflow_usage(session, window, ignored)
            top_users = await queries.get_top_users(
                session, window, _TOP_USERS_LIMIT, ignored
            )

    return AdminDashboardResponse(
        period_days=window.days,
        period_start=window.start,
        period_end=window.end,
        granularity=window.granularity,
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        ignored_user_ids=ignored,
        total_users=total_users,
        active_users=active_users,
        new_users=new_users,
        projects_created=projects_created,
        assessments_run=assessments_run,
        feedback_received=feedback_received,
        activity=activity,
        workflows=workflows,
        top_users=top_users,
        feedback=feedback,
    )
