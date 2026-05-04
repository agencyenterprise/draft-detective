"""add workflow run failure + heartbeat fields

Revision ID: 6f5eebe4f144
Revises: f4ef6e0d9708
Create Date: 2026-05-04 10:54:20.375734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = '6f5eebe4f144'
down_revision: Union[str, None] = 'f4ef6e0d9708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sa.Enum('TIMEOUT', 'DEPENDENCY_TIMEOUT', 'NO_HEARTBEAT', 'UNHANDLED_EXCEPTION', name='workflowrunfailurereason').create(op.get_bind())
    op.sync_enum_values(
        enum_schema='public',
        enum_name='workflowrunstatus',
        new_values=['PENDING', 'RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED'],
        affected_columns=[TableReference(table_schema='public', table_name='workflow_runs', column_name='status', existing_server_default="'COMPLETED'::workflowrunstatus")],
        enum_values_to_rename=[],
    )
    op.add_column('workflow_runs', sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workflow_runs', sa.Column('failure_reason', sa.Enum('TIMEOUT', 'DEPENDENCY_TIMEOUT', 'NO_HEARTBEAT', 'UNHANDLED_EXCEPTION', name='workflowrunfailurereason'), nullable=True))
    op.add_column('workflow_runs', sa.Column('failure_message', sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column('workflow_runs', 'failure_message')
    op.drop_column('workflow_runs', 'failure_reason')
    op.drop_column('workflow_runs', 'heartbeat_at')
    op.sync_enum_values(
        enum_schema='public',
        enum_name='workflowrunstatus',
        new_values=['PENDING', 'RUNNING', 'COMPLETED', 'CANCELLED'],
        affected_columns=[TableReference(table_schema='public', table_name='workflow_runs', column_name='status', existing_server_default="'COMPLETED'::workflowrunstatus")],
        enum_values_to_rename=[],
    )
    sa.Enum('TIMEOUT', 'DEPENDENCY_TIMEOUT', 'NO_HEARTBEAT', 'UNHANDLED_EXCEPTION', name='workflowrunfailurereason').drop(op.get_bind())
