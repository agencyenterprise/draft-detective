"""add workflow gate approvals and awaiting_approval status

Revision ID: a3c9e1f5b7d2
Revises: d7e75e8c6728
Create Date: 2026-09-02 12:00:00.000000

Replaces the retired ``human_approval`` workflow with a consent gate:

- ``workflow_runs.status`` gains ``AWAITING_APPROVAL`` for runs waiting on a gate.
- ``workflow_gate_approvals`` records, per project revision, which gates the
  user has approved.
- Data: every completed ``human_approval`` run becomes a ``reference_review``
  approval for its project revision, so already-approved revisions don't ask
  again. Projects mid-review at deploy time (a PENDING ``human_approval`` row)
  have that row cancelled and their sibling PENDING
  ``claim_reference_validation_v2`` row moved to ``AWAITING_APPROVAL``, so the
  user can still click Approve after the deploy.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = 'a3c9e1f5b7d2'
down_revision: Union[str, None] = 'd7e75e8c6728'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_COLUMN = TableReference(
    table_schema='public',
    table_name='workflow_runs',
    column_name='status',
    existing_server_default="'COMPLETED'::workflowrunstatus",
)


def upgrade() -> None:
    # ADD VALUE appends to the existing type in place. The alternative,
    # op.sync_enum_values, recreates the type and re-casts the column, which
    # rewrites every workflow_runs row (and its multi-MB state_json TOAST) —
    # seconds locally, longer in production. ADD VALUE cannot run inside a
    # transaction, hence the autocommit block; the data steps below run in a
    # fresh transaction afterwards, where the new value is usable.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE workflowrunstatus ADD VALUE IF NOT EXISTS 'AWAITING_APPROVAL'")

    op.create_table(
        'workflow_gate_approvals',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('gate', sa.String(length=64), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_by_user_id', sa.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id', 'revision', 'gate',
            name='uq_workflow_gate_approvals_project_revision_gate',
        ),
    )
    op.create_index(
        op.f('ix_workflow_gate_approvals_project_id'),
        'workflow_gate_approvals',
        ['project_id'],
        unique=False,
    )

    _backfill_reference_review_approvals()
    _hold_in_flight_reviews()


def _backfill_reference_review_approvals() -> None:
    """One reference_review approval per project revision with a completed human_approval run."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT ON (project_id, revision)
                   project_id, revision, COALESCE(completed_at, last_updated_at) AS approved_at
            FROM workflow_runs
            WHERE type = 'human_approval'
              AND status = 'COMPLETED'
              AND project_id IS NOT NULL
            ORDER BY project_id, revision, COALESCE(completed_at, last_updated_at) ASC
            """
        )
    ).fetchall()
    if not rows:
        return
    approvals = sa.table(
        'workflow_gate_approvals',
        sa.column('id', sa.UUID(as_uuid=True)),
        sa.column('project_id', sa.UUID(as_uuid=True)),
        sa.column('revision', sa.Integer()),
        sa.column('gate', sa.String()),
        sa.column('approved_at', sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        approvals,
        [
            {
                'id': uuid.uuid4(),
                'project_id': row.project_id,
                'revision': row.revision,
                'gate': 'reference_review',
                'approved_at': row.approved_at,
            }
            for row in rows
        ],
    )


def _hold_in_flight_reviews() -> None:
    """Move claim_reference_validation_v2 runs waiting on a pending human_approval run to AWAITING_APPROVAL."""
    op.execute(
        sa.text(
            """
            UPDATE workflow_runs AS dependent
            SET status = 'AWAITING_APPROVAL'
            FROM workflow_runs AS gate
            WHERE gate.type = 'human_approval'
              AND gate.status = 'PENDING'
              AND dependent.project_id = gate.project_id
              AND dependent.revision = gate.revision
              AND dependent.type = 'claim_reference_validation_v2'
              AND dependent.status = 'PENDING'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE workflow_runs
            SET status = 'CANCELLED', completed_at = NOW()
            WHERE type = 'human_approval'
              AND status = 'PENDING'
            """
        )
    )


def downgrade() -> None:
    # Rows holding the removed value would make the enum sync fail; a run
    # awaiting approval is closest to PENDING from the old code's point of view.
    op.execute(
        sa.text("UPDATE workflow_runs SET status = 'PENDING' WHERE status = 'AWAITING_APPROVAL'")
    )
    op.drop_index(op.f('ix_workflow_gate_approvals_project_id'), table_name='workflow_gate_approvals')
    op.drop_table('workflow_gate_approvals')
    op.sync_enum_values(
        enum_schema='public',
        enum_name='workflowrunstatus',
        new_values=['PENDING', 'RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED'],
        affected_columns=[_STATUS_COLUMN],
        enum_values_to_rename=[],
    )
