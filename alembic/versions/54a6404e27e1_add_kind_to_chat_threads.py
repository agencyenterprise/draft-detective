"""add kind to chat_threads

Which agent a thread talks to: the /chat assistant or the live-report orchestrator.
Stacked on the run-per-type limits (d4b8f1a6c2e9); existing threads are chat.

Revision ID: 54a6404e27e1
Revises: d4b8f1a6c2e9
Create Date: 2026-11-06 18:40:33.527222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '54a6404e27e1'
down_revision: Union[str, None] = 'd4b8f1a6c2e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_threads', sa.Column('kind', sa.String(), server_default='chat', nullable=False))


def downgrade() -> None:
    op.drop_column('chat_threads', 'kind')
