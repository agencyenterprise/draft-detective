"""The overview reads each run's state_json as little as it can.

Every path read straight off `state_json` decompresses the whole value, tens of
MB for document processing, and the page polls the overview every few seconds.
The overview therefore decompresses each state once, into a lateral copy, and
reads every path from that copy.
"""

from sqlalchemy.dialects import postgresql

from lib.services.projects.overview import _overview_runs_stmt

_DIALECT = postgresql.dialect()


def _sql() -> str:
    return str(_overview_runs_stmt("project", 2).compile(dialect=_DIALECT))


def _lateral() -> str:
    """The lateral subquery that copies the state, as SQL."""
    return _sql().split("LEFT OUTER JOIN LATERAL", 1)[1].split(" ON true", 1)[0]


def test_only_errors_reference_count_and_main_file_path_are_read() -> None:
    state_columns = {
        str(column.key)
        for column in _overview_runs_stmt("project", 2).selected_columns
        if ".state[" in str(column.compile(dialect=_DIALECT))
    }
    assert state_columns == {"errors", "ref_count", "main_file_path"}


def test_no_path_is_read_straight_off_the_state_column() -> None:
    sql = _sql()

    assert "state_json[" not in sql
    assert "state_json ->" not in sql


def test_the_state_is_copied_once_in_a_lateral_the_planner_cannot_inline() -> None:
    lateral = _lateral()

    assert lateral.startswith(" (SELECT workflow_runs.state_json || '{}'::jsonb")
    # Inlined, each path would read the column again; OFFSET keeps it a subquery.
    assert "OFFSET" in lateral
    # Correlated to the outer run, not a scan of the whole table.
    assert "FROM workflow_runs" not in lateral
