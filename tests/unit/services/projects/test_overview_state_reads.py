"""The overview reads each run's state_json as little as it can.

Every path read from `state_json` decompresses the whole value, several MB for
document processing, and the page polls the overview every few seconds. A
path that only one run type needs must therefore be guarded by that type, so
the other runs' states are never decompressed for it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from lib.services.projects.overview import _overview_runs_stmt
from lib.services.projects.overview_state_cache import (
    CachedRunState,
    RunStateCache,
    RunStateFields,
)


def _state_columns() -> dict[str, str]:
    """The overview's state-reading columns, compiled to SQL, by label."""
    stmt = _overview_runs_stmt("project", 2)
    dialect = postgresql.dialect()
    return {
        str(column.key): str(
            column.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
        )
        for column in stmt.selected_columns
        # The bare column is deferred: listed here, but never in the SQL.
        if column.key != "state_json"
        and "state_json" in str(column.compile(dialect=dialect))
    }


def test_only_errors_are_read_from_every_run() -> None:
    assert set(_state_columns()) == {"errors", "ref_count", "main_file_path"}


def test_reference_count_is_read_only_from_reference_extraction() -> None:
    sql = _state_columns()["ref_count"]
    assert sql.startswith("CASE WHEN (workflow_runs.type = 'reference_extraction')")


def test_main_file_path_is_read_only_from_document_processing() -> None:
    sql = _state_columns()["main_file_path"]
    assert sql.startswith("CASE WHEN (workflow_runs.type = 'document_processing')")


def test_runs_already_read_at_their_version_are_not_read_again() -> None:
    known = [(uuid.uuid4(), datetime(2026, 11, 6, tzinfo=UTC))]
    stmt = _overview_runs_stmt("project", 2, known)
    dialect = postgresql.dialect()
    for column in stmt.selected_columns:
        sql = str(column.compile(dialect=dialect))
        if column.key != "state_json" and "state_json" in sql:
            assert sql.startswith(
                "CASE WHEN ((workflow_runs.id, workflow_runs.last_updated_at) IN"
            ), column.key


def test_the_cache_forgets_the_least_recently_read_revision() -> None:
    cache = RunStateCache(max_revisions=2)
    entry = {
        uuid.uuid4(): CachedRunState(
            version=datetime(2026, 11, 6, tzinfo=UTC), fields=RunStateFields()
        )
    }
    cache.store(("a", 1), entry)
    cache.store(("b", 1), entry)
    cache.known(("a", 1))  # read, so "b" is now the oldest
    cache.store(("c", 1), entry)

    assert cache.known(("a", 1)) == entry
    assert cache.known(("b", 1)) == {}
    assert cache.known(("c", 1)) == entry
