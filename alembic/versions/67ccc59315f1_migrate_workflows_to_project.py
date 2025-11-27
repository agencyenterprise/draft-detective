"""migrate_workflows_to_project

Revision ID: 67ccc59315f1
Revises: 063d05606fe7
Create Date: 2025-11-27 15:49:12.894428

"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "67ccc59315f1"
down_revision: Union[str, None] = "063d05606fe7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Create table objects for reflection
    workflow_runs = sa.table(
        "workflow_runs",
        sa.column("id", sa.UUID),
        sa.column("title", sa.String),
        sa.column("user_id", sa.UUID),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_updated_at", sa.DateTime(timezone=True)),
        sa.column("project_id", sa.UUID),
    )

    projects = sa.table(
        "projects",
        sa.column("id", sa.UUID),
        sa.column("title", sa.String),
        sa.column("user_id", sa.UUID),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_updated_at", sa.DateTime(timezone=True)),
    )

    # Fetch all workflow runs
    select_stmt = sa.select(
        workflow_runs.c.id,
        workflow_runs.c.title,
        workflow_runs.c.user_id,
        workflow_runs.c.created_at,
        workflow_runs.c.last_updated_at,
    )

    workflow_runs_data = connection.execute(select_stmt).fetchall()

    # For each workflow run, create a project and update the workflow_run
    for wr in workflow_runs_data:
        project_id = uuid.uuid4()

        # Insert project
        insert_project = projects.insert().values(
            id=project_id,
            title=wr.title,
            user_id=wr.user_id,
            created_at=wr.created_at,
            last_updated_at=wr.last_updated_at,
        )
        connection.execute(insert_project)

        # Update workflow_run with project_id
        update_workflow_run = (
            workflow_runs.update()
            .where(workflow_runs.c.id == wr.id)
            .values(project_id=project_id)
        )
        connection.execute(update_workflow_run)


def downgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Set all workflow_run.project_id to NULL
    workflow_runs = sa.table(
        "workflow_runs",
        sa.column("project_id", sa.UUID),
    )

    update_stmt = workflow_runs.update().values(project_id=None)
    connection.execute(update_stmt)

    # Delete all projects that were created by this migration
    # Note: This assumes all projects were created by this migration
    # If there are other projects, this will delete them too
    projects = sa.table("projects")
    delete_stmt = sa.delete(projects)
    connection.execute(delete_stmt)
