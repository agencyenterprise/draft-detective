"""add procrastinate schema

Installs the job queue's tables, types, functions and triggers. The SQL is a
frozen copy of the schema that procrastinate 3.11.0 ships, so this migration
builds the same database whatever version is installed later. Upgrading
procrastinate past a version that ships SQL migrations (its
`procrastinate/sql/migrations/`) needs a new Alembic migration that applies
those scripts.

Revision ID: 724c774cd57a
Revises: c7e2a9d41f03
Create Date: 2026-11-12 18:45:00.000000

"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "724c774cd57a"
down_revision: str | None = "c7e2a9d41f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_SQL = Path(__file__).parent.parent / "sql" / "procrastinate_03.11.00_schema.sql"


def upgrade() -> None:
    # Sent to the driver as is, so SQLAlchemy reads no `:name` binds in the casts.
    # The driver still formats `%` placeholders, so the literal ones in the RAISE
    # messages are doubled, as procrastinate's own `apply_schema` does.
    schema = SCHEMA_SQL.read_text(encoding="utf-8").replace("%", "%%")
    op.get_bind().exec_driver_sql(schema)


def downgrade() -> None:
    # Dropping the tables takes their triggers and indexes with them.
    op.execute(
        "DROP TABLE IF EXISTS procrastinate_events, procrastinate_periodic_defers, "
        "procrastinate_jobs, procrastinate_workers CASCADE"
    )
    op.execute(
        r"""
        DO $$
        DECLARE fn regprocedure;
        BEGIN
            FOR fn IN
                SELECT p.oid::regprocedure FROM pg_proc p
                WHERE p.pronamespace = current_schema()::regnamespace
                AND p.proname LIKE 'procrastinate\_%'
            LOOP
                EXECUTE 'DROP FUNCTION ' || fn;
            END LOOP;
        END;
        $$
        """
    )
    op.execute(
        "DROP TYPE IF EXISTS procrastinate_job_to_defer_v1, "
        "procrastinate_job_event_type, procrastinate_job_status"
    )
