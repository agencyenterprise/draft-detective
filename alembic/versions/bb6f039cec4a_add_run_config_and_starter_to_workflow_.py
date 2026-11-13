"""add run config and starter to workflow runs

The job queue runs a workflow from its run id alone, so the run keeps what the
start request knew: the config (without its API key) and the user who started
it. Rows created before this migration have neither; the job then builds the
config from the project and runs without a user.

Revision ID: bb6f039cec4a
Revises: 724c774cd57a
Create Date: 2026-11-13 10:01:22.310731

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb6f039cec4a"
down_revision: str | None = "724c774cd57a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "workflow_runs",
        sa.Column("started_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_runs_started_by_user_id_users",
        "workflow_runs",
        "users",
        ["started_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflow_runs_started_by_user_id_users",
        "workflow_runs",
        type_="foreignkey",
    )
    op.drop_column("workflow_runs", "started_by_user_id")
    op.drop_column("workflow_runs", "config_json")
