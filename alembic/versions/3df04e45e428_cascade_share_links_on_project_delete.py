"""delete a project's share links when the project is deleted

Revision ID: 3df04e45e428
Revises: d4b8f1a6c2e9
Create Date: 2026-11-24 16:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3df04e45e428"
down_revision: str | None = "d4b8f1a6c2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "share_links_resource_id_fkey"


def upgrade() -> None:
    # Links of projects deleted before this migration would fail the new
    # foreign key: they point at nothing and grant no access, so drop them.
    op.execute(
        "DELETE FROM share_links s "
        "WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = s.resource_id)"
    )
    op.create_foreign_key(
        CONSTRAINT,
        "share_links",
        "projects",
        ["resource_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # The deleted orphan links are not restored.
    op.drop_constraint(CONSTRAINT, "share_links", type_="foreignkey")
