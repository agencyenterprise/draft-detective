"""The migration that adds the one-running and one-waiting indexes applies on a
database holding the duplicates the old start paths could create.

Runs on a scratch database of its own, migrated to the revision before, so the
shared test database is never downgraded under the other tests.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from tests.integration_db import REPO_ROOT, _script, is_test_database, libpq_url

REVISION = "d4b8f1a6c2e9"
PROJECT = uuid.uuid4()


@pytest.fixture
def scratch_database() -> Iterator[URL]:
    base = make_url(os.environ["TEST_DATABASE_URL"])
    url = base.set(database=f"unique_runs_mig_{uuid.uuid4().hex[:8]}_test")
    assert is_test_database(url)
    identifier = sql.Identifier(url.database or "")
    admin_url = libpq_url(base.set(database="postgres"))
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(identifier))
    try:
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(identifier)
            )


def _migrate(url: URL, target: str, direction: str = "upgrade") -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": libpq_url(url)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr


def _seed(
    conn: psycopg.Connection, rows: list[tuple[str, str, int]]
) -> list[uuid.UUID]:
    """Insert runs of PROJECT as (type, status, minutes after a base time)."""
    user = uuid.uuid4()
    conn.execute(
        "INSERT INTO users (id, email, name, created_at, last_updated_at) "
        "VALUES (%s, %s, 'mig', now(), now())",
        (user, f"mig-{user}@example.com"),
    )
    conn.execute(
        "INSERT INTO projects (id, user_id, title, created_at, last_updated_at, "
        "current_revision) VALUES (%s, %s, 'mig', now(), now(), 1)",
        (PROJECT, user),
    )
    ids = []
    for workflow_type, status, minute in rows:
        run_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO workflow_runs (id, project_id, type, langgraph_thread_id, "
            "status, created_at, last_updated_at, revision) VALUES (%s, %s, %s, "
            "%s, %s, timestamp '2026-01-01' + make_interval(mins => %s), now(), 1)",
            (run_id, PROJECT, workflow_type, str(uuid.uuid4()), status, minute),
        )
        ids.append(run_id)
    return ids


def _statuses(conn: psycopg.Connection, ids: list[uuid.UUID]) -> list[str]:
    rows = conn.execute(
        "SELECT id, status, completed_at IS NOT NULL FROM workflow_runs "
        "WHERE id = ANY(%s)",
        (ids,),
    ).fetchall()
    by_id = {row[0]: (row[1], row[2]) for row in rows}
    # A cancelled duplicate is marked ended.
    assert all(ended for status, ended in by_id.values() if status == "CANCELLED")
    return [by_id[run_id][0] for run_id in ids]


def test_migration_cancels_duplicate_active_runs_and_builds_the_indexes(
    scratch_database: URL,
) -> None:
    before = _script().get_revision(REVISION).down_revision
    assert isinstance(before, str)
    _migrate(scratch_database, before)
    with psycopg.connect(libpq_url(scratch_database), autocommit=True) as conn:
        ids = _seed(
            conn,
            [
                ("abbreviation_scan_v2", "RUNNING", 0),
                ("abbreviation_scan_v2", "RUNNING", 1),
                ("abbreviation_scan_v2", "PENDING", 2),
                ("abbreviation_scan_v2", "AWAITING_APPROVAL", 3),
                ("abbreviation_scan_v2", "PENDING", 4),
                ("abbreviation_scan_v2", "COMPLETED", 5),
                ("review_assistant", "RUNNING", 0),
                ("review_assistant", "RUNNING", 1),
                ("review_assistant", "PENDING", 2),
                ("review_assistant", "PENDING", 3),
            ],
        )

    _migrate(scratch_database, REVISION)

    with psycopg.connect(libpq_url(scratch_database), autocommit=True) as conn:
        assert _statuses(conn, ids) == [
            # The newest RUNNING and the newest waiting run stay.
            "CANCELLED",
            "RUNNING",
            "CANCELLED",
            "CANCELLED",
            "PENDING",
            "COMPLETED",
            # Independent runs are left alone.
            "RUNNING",
            "RUNNING",
            "PENDING",
            "PENDING",
        ]
        flags = conn.execute(
            "SELECT DISTINCT type, independent_run FROM workflow_runs ORDER BY type"
        ).fetchall()
        assert flags == [("abbreviation_scan_v2", False), ("review_assistant", True)]
        with pytest.raises(psycopg.errors.UniqueViolation):
            _seed_waiting(conn, "AWAITING_APPROVAL")

    # And it goes back down cleanly.
    _migrate(scratch_database, before, direction="downgrade")


def _seed_waiting(conn: psycopg.Connection, status: str) -> None:
    conn.execute(
        "INSERT INTO workflow_runs (id, project_id, type, langgraph_thread_id, "
        "status, created_at, last_updated_at, revision) VALUES (%s, %s, "
        "'abbreviation_scan_v2', %s, %s, now(), now(), 1)",
        (uuid.uuid4(), PROJECT, str(uuid.uuid4()), status),
    )
