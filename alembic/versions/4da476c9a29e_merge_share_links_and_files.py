"""merge_share_links_and_files

Revision ID: 4da476c9a29e
Revises: a1b2c3d4e5f6, cdfa040a0771
Create Date: 2025-12-10 20:27:31.862486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4da476c9a29e'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'cdfa040a0771')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
