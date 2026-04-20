"""add mcp_oauth_kv table for multi-pod OAuth state

Revision ID: 3b1c8a9d2f04
Revises: 8ece42fd6856
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "3b1c8a9d2f04"
down_revision: Union[str, None] = "8ece42fd6856"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_kv",
        sa.Column("collection", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("collection", "key"),
    )
    op.create_index(
        "ix_mcp_oauth_kv_expires_at",
        "mcp_oauth_kv",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_oauth_kv_expires_at", table_name="mcp_oauth_kv")
    op.drop_table("mcp_oauth_kv")
