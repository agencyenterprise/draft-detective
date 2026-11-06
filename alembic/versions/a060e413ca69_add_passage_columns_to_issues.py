"""add passage columns to issues

Revision ID: a060e413ca69
Revises: 5e2a9c4b7d81
Create Date: 2026-11-04 17:32:32.250742

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a060e413ca69"
down_revision: str | None = "5e2a9c4b7d81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("passage_text", sa.Text(), nullable=True))
    op.add_column("issues", sa.Column("passage_display_text", sa.Text(), nullable=True))
    op.add_column(
        "issues", sa.Column("passage_display_occurrence", sa.Integer(), nullable=True)
    )
    op.add_column("issues", sa.Column("passage_line", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("issues", "passage_line")
    op.drop_column("issues", "passage_display_occurrence")
    op.drop_column("issues", "passage_display_text")
    op.drop_column("issues", "passage_text")
