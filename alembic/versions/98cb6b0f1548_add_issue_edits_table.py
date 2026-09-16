"""add issue_edits table

Revision ID: 98cb6b0f1548
Revises: 284108200780
Create Date: 2026-09-15 16:43:19.893838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '98cb6b0f1548'
down_revision: Union[str, None] = '284108200780'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Proposed edits move out of the JSONB `issues.edits` column into their
    # own table. Rows share their issue's lifecycle: cascaded on delete,
    # archived with it, ordered by `position`.
    #
    # `create_table` emits CREATE TYPE for the inline enum, so the type is
    # not created separately here; the downgrade drops it explicitly.
    op.create_table('issue_edits',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('issue_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('original_text', sa.Text(), nullable=False),
    sa.Column('replacement_text', sa.Text(), nullable=False),
    sa.Column('start_line', sa.Integer(), nullable=False),
    sa.Column('end_line', sa.Integer(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PROPOSED', 'ACCEPTED', 'REJECTED', name='issueeditstatus'), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_issue_edits_issue_id'), 'issue_edits', ['issue_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_issue_edits_issue_id'), table_name='issue_edits')
    op.drop_table('issue_edits')
    sa.Enum('PROPOSED', 'ACCEPTED', 'REJECTED', name='issueeditstatus').drop(op.get_bind())
