"""drop issues chunk_indices

Revision ID: 13b5e3777017
Revises: f1c32f2aa9ee
Create Date: 2026-11-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "13b5e3777017"
down_revision: str | None = "f1c32f2aa9ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy column: no workflow has populated it since issues moved to line
    # ranges. Its remaining values are dropped with it.
    op.drop_column("issues", "chunk_indices")


def downgrade() -> None:
    op.add_column(
        "issues",
        sa.Column("chunk_indices", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
