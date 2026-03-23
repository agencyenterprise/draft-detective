"""add_pg_trgm_extension

Revision ID: b3d7e9f12a45
Revises: 1cc768ae2623
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3d7e9f12a45"
down_revision: Union[str, None] = "1cc768ae2623"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm CASCADE")
