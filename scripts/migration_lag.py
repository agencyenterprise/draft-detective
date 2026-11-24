"""Say whether the `.env` database is at this checkout's migration head.

`scripts/e2e_instance.sh` runs this after it starts a private instance. The
instance shares the user's dev database, and when that database is behind the
branch's migrations, routes that touch the new columns fail with
`UndefinedColumn`, which looks like a bug in the change under test. Printing
the difference up front saves the end-to-end check from finding it in the log.

Read-only: it reads `alembic_version` and never migrates. Prints nothing when
the database is at head or can't be read (the instance reports that).

    uv run python -m scripts.migration_lag
"""

import sys
from pathlib import Path

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from lib.config.env import config

REPO_ROOT = Path(__file__).resolve().parents[1]
CONNECT_TIMEOUT_SECONDS = 5
# A migration running in another session can hold a lock on alembic_version.
STATEMENT_TIMEOUT_MS = 5000


def describe_lag(
    applied: set[str], heads: set[str], known: set[str], database: str
) -> str | None:
    """A warning when the database isn't at this checkout's head, else None."""
    if applied == heads:
        return None
    found = ", ".join(sorted(applied)) or "none"
    expected = ", ".join(sorted(heads))
    if not applied <= known:
        return (
            f"note: the database {database} is at {found}, a migration from another branch; "
            f"this checkout's head is {expected}. That's usually harmless when it only adds columns. "
            "If routes fail with UndefinedColumn or NotNullViolation, don't run Alembic: tell the user."
        )
    return (
        f"warning: the database {database} is behind this checkout's migrations: it is at {found}, "
        f"this checkout's head is {expected}. Routes that touch the new columns fail "
        "(the backend log shows UndefinedColumn). Don't run Alembic: tell the user, "
        "who applies migrations to this database."
    )


def libpq_url(url: str) -> str:
    """psycopg rejects a SQLAlchemy dialect suffix such as `postgresql+psycopg://`."""
    return (
        make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    )


def applied_revisions(url: str) -> tuple[str, set[str]]:
    """The database libpq connected to, and the revisions in its alembic_version."""
    with psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS) as conn:
        # Set on the session, so the URL's own `options` (search_path) still apply.
        conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        table = conn.execute("SELECT to_regclass('alembic_version')").fetchone()
        if not table or table[0] is None:
            return conn.info.dbname, set()
        rows = conn.execute("SELECT version_num FROM alembic_version")
        return conn.info.dbname, {row[0] for row in rows}


def migration_scripts() -> ScriptDirectory:
    alembic_config = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return ScriptDirectory.from_config(alembic_config)


def main() -> None:
    try:
        database, applied = applied_revisions(libpq_url(config.DATABASE_URL))
    except psycopg.Error:
        return
    script = migration_scripts()
    known = {revision.revision for revision in script.walk_revisions()}
    warning = describe_lag(applied, set(script.get_heads()), known, database)
    if warning:
        print(warning, file=sys.stderr)


if __name__ == "__main__":
    main()
