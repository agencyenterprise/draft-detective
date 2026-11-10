"""unique active workflow progress entry per run and name

Revision ID: c7e2a9d41f03
Revises: b110b187e1cd
Create Date: 2026-11-10 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2a9d41f03"
down_revision: str | None = "b110b187e1cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Block writes and row-locking reads until the migration commits, so workers
    # on the old code can't add a duplicate before the index is built, nor hold
    # a row lock the cleanup would wait on (a deadlock under a weaker lock).
    op.execute("LOCK TABLE workflow_progress IN EXCLUSIVE MODE")
    # Close duplicate active entries left by the old in-process lock, keeping
    # the oldest per (run, name), so the unique index can be built.
    op.execute(
        """
        UPDATE workflow_progress AS wp
        SET completed_at = now()
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY workflow_run_id, name ORDER BY created_at, id
            ) AS rn
            FROM workflow_progress
            WHERE completed_at IS NULL
        ) AS dup
        WHERE wp.id = dup.id AND dup.rn > 1
        """
    )
    op.create_index(
        "uq_workflow_progress_active_run_name",
        "workflow_progress",
        ["workflow_run_id", "name"],
        unique=True,
        postgresql_where=sa.text("completed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workflow_progress_active_run_name",
        table_name="workflow_progress",
        postgresql_where=sa.text("completed_at IS NULL"),
    )
