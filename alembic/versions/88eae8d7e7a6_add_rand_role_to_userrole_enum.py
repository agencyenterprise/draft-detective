"""Add RAND role to UserRole enum

Revision ID: 88eae8d7e7a6
Revises: 3f207b45e735
Create Date: 2026-02-03 11:17:36.809746

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = "88eae8d7e7a6"
down_revision: Union[str, None] = "3f207b45e735"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE 'RAND'")


def downgrade() -> None:
    op.execute("ALTER TYPE userrole DROP VALUE 'RAND'")
