"""share links belong to a project and go with it

Revision ID: 3df04e45e428
Revises: 54a6404e27e1
Create Date: 2026-11-24 16:30:00.000000

share_links pointed at any resource through resource_type + resource_id, with
no foreign key, so deleting a project left its links behind. Projects are the
only resource ever shared: resource_id becomes project_id, a foreign key to
projects with ON DELETE CASCADE, and resource_type goes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3df04e45e428"
down_revision: str | None = "54a6404e27e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOREIGN_KEY = "share_links_project_id_fkey"


def upgrade() -> None:
    # Links of projects deleted before this migration would fail the new
    # foreign key: they point at nothing and grant no access, so drop them.
    op.execute(
        "DELETE FROM share_links s "
        "WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = s.resource_id)"
    )
    op.alter_column("share_links", "resource_id", new_column_name="project_id")
    op.execute(
        "ALTER INDEX ix_share_links_resource_id RENAME TO ix_share_links_project_id"
    )
    op.drop_column("share_links", "resource_type")
    op.create_foreign_key(
        FOREIGN_KEY,
        "share_links",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # The orphan links deleted on upgrade are not restored.
    op.drop_constraint(FOREIGN_KEY, "share_links", type_="foreignkey")
    op.add_column(
        "share_links",
        sa.Column(
            "resource_type",
            sa.String(length=50),
            nullable=False,
            server_default="project",
        ),
    )
    op.alter_column("share_links", "resource_type", server_default=None)
    op.execute(
        "ALTER INDEX ix_share_links_project_id RENAME TO ix_share_links_resource_id"
    )
    op.alter_column("share_links", "project_id", new_column_name="resource_id")
