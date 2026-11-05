"""drop feedback entity_path

Revision ID: 5e2a9c4b7d81
Revises: 13b5e3777017
Create Date: 2026-11-05 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5e2a9c4b7d81"
down_revision: str | None = "13b5e3777017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Feedback that isn't on an issue came only from the retired chunk/claim
    # pipeline, addressed by entity_path. Nothing reads it any more, so those
    # rows go, and every remaining row must point at an issue.
    op.execute("DELETE FROM feedback WHERE issue_id IS NULL")
    op.drop_column("feedback", "entity_path")
    op.alter_column("feedback", "issue_id", nullable=False)


def downgrade() -> None:
    # The deleted chunk and claim feedback is not restored.
    op.alter_column("feedback", "issue_id", nullable=True)
    op.add_column(
        "feedback",
        sa.Column(
            "entity_path",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("feedback", "entity_path", server_default=None)
