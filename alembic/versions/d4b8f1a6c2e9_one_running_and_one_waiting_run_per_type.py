"""one running and one waiting workflow run per project, revision and type

Revision ID: d4b8f1a6c2e9
Revises: c7e2a9d41f03
Create Date: 2026-11-12 18:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b8f1a6c2e9"
down_revision: str | None = "c7e2a9d41f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Workflows whose manifest sets independent_runs today. The flag is copied onto
# each new row by the application; this backfills the rows that exist.
INDEPENDENT_TYPES = ("review_assistant",)

RUNNING_PREDICATE = "status = 'RUNNING' AND NOT independent_run"
WAITING_PREDICATE = "status IN ('PENDING', 'AWAITING_APPROVAL') AND NOT independent_run"


def upgrade() -> None:
    # Block writes and row-locking reads until the migration commits, so
    # workers on the old code can't add a duplicate before the indexes exist.
    op.execute("LOCK TABLE workflow_runs IN EXCLUSIVE MODE")
    op.add_column(
        "workflow_runs",
        sa.Column(
            "independent_run",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE workflow_runs SET independent_run = true WHERE type IN :types"
        ).bindparams(sa.bindparam("types", INDEPENDENT_TYPES, expanding=True))
    )
    # End the duplicates the old start paths could create: per project,
    # revision and type keep the newest RUNNING run and the newest waiting one,
    # and cancel the rest, so the unique indexes can be built.
    op.execute(
        """
        UPDATE workflow_runs AS wr
        SET status = 'CANCELLED', completed_at = now(), last_updated_at = now()
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY project_id, revision, type, status = 'RUNNING'
                ORDER BY created_at DESC, id DESC
            ) AS rn
            FROM workflow_runs
            WHERE status IN ('PENDING', 'RUNNING', 'AWAITING_APPROVAL')
              AND NOT independent_run
        ) AS dup
        WHERE wr.id = dup.id AND dup.rn > 1
        """
    )
    op.create_index(
        "uq_workflow_runs_one_running",
        "workflow_runs",
        ["project_id", "revision", "type"],
        unique=True,
        postgresql_where=sa.text(RUNNING_PREDICATE),
    )
    op.create_index(
        "uq_workflow_runs_one_waiting",
        "workflow_runs",
        ["project_id", "revision", "type"],
        unique=True,
        postgresql_where=sa.text(WAITING_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workflow_runs_one_waiting",
        table_name="workflow_runs",
        postgresql_where=sa.text(WAITING_PREDICATE),
    )
    op.drop_index(
        "uq_workflow_runs_one_running",
        table_name="workflow_runs",
        postgresql_where=sa.text(RUNNING_PREDICATE),
    )
    op.drop_column("workflow_runs", "independent_run")
