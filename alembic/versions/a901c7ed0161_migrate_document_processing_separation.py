"""migrate_document_processing_separation

Revision ID: a901c7ed0161
Revises: 4da476c9a29e
Create Date: 2025-12-18 10:42:05.108967

Migrate existing claim_substantiation workflows to separated architecture.
Creates new DOCUMENT_PROCESSING workflows with extracted artifacts from
completed claim_substantiation workflows.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import select, and_

# revision identifiers, used by Alembic.
revision: str = "a901c7ed0161"
down_revision: Union[str, None] = "4da476c9a29e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Migrate existing claim_substantiation workflows to separated architecture.
    Creates new DOCUMENT_PROCESSING workflows with extracted artifacts.
    """
    asyncio.run(async_upgrade())


def downgrade() -> None:
    """
    Remove DOCUMENT_PROCESSING workflows created by this migration.
    """
    connection = op.get_bind()

    workflow_runs = sa.table(
        "workflow_runs",
        sa.column("type", sa.String),
    )

    delete_stmt = workflow_runs.delete().where(
        workflow_runs.c.type == "document_processing"
    )
    connection.execute(delete_stmt)

    logger.info("Deleted all DOCUMENT_PROCESSING workflow runs")


async def async_upgrade():
    """Async migration logic using LangGraph checkpointer."""
    from lib.workflows.checkpointer import get_checkpointer
    from lib.workflows.registry import create_graph
    from lib.workflows.models import WorkflowRunType
    from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
    from lib.workflows.document_processing.state import (
        DocumentProcessingState,
        DocumentProcessingWorkflowConfig,
        DocumentChunk as DocProcessingChunk,
    )

    connection = op.get_bind()

    workflow_runs = sa.table(
        "workflow_runs",
        sa.column("id", sa.dialects.postgresql.UUID),
        sa.column("project_id", sa.dialects.postgresql.UUID),
        sa.column("type", sa.String),
        sa.column("status", sa.String),
        sa.column("langgraph_thread_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_updated_at", sa.DateTime(timezone=True)),
    )

    select_stmt = select(
        workflow_runs.c.id,
        workflow_runs.c.project_id,
        workflow_runs.c.langgraph_thread_id,
        workflow_runs.c.created_at,
    ).where(
        and_(
            workflow_runs.c.type == "claim_substantiation",
            sa.cast(workflow_runs.c.status, sa.String) == "COMPLETED",
        )
    )

    claim_workflows = connection.execute(select_stmt).fetchall()

    logger.info(
        f"Found {len(claim_workflows)} claim_substantiation workflows to migrate"
    )

    if not claim_workflows:
        logger.info("No workflows to migrate")
        return

    new_records = []

    async with get_checkpointer() as checkpointer:
        claim_graph = create_graph(WorkflowRunType.CLAIM_SUBSTANTIATION)
        claim_app = claim_graph.compile(checkpointer=checkpointer)

        doc_processing_graph = create_graph(WorkflowRunType.DOCUMENT_PROCESSING)
        doc_processing_app = doc_processing_graph.compile(checkpointer=checkpointer)

        for workflow in claim_workflows:
            try:
                state_snapshot = await claim_app.aget_state(
                    {"configurable": {"thread_id": workflow.langgraph_thread_id}}
                )

                if not state_snapshot.values:
                    logger.warning(f"Skipping workflow {workflow.id}: no state found")
                    continue

                claim_state = ClaimSubstantiatorState(**state_snapshot.values)

                if not claim_state.chunks:
                    logger.warning(f"Skipping workflow {workflow.id}: no chunks found")
                    continue

                if not claim_state.file:
                    logger.warning(f"Skipping workflow {workflow.id}: no file found")
                    continue

                doc_processing_chunks = [
                    DocProcessingChunk(
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        paragraph_index=chunk.paragraph_index,
                    )
                    for chunk in claim_state.chunks
                ]

                doc_processing_state = DocumentProcessingState(
                    config=DocumentProcessingWorkflowConfig(
                        project_id=str(workflow.project_id),
                    ),
                    file=claim_state.file,
                    supporting_files=claim_state.supporting_files or [],
                    main_document_summary=claim_state.main_document_summary,
                    supporting_documents_summaries=claim_state.supporting_documents_summaries
                    or {},
                    chunks=doc_processing_chunks,
                    chunk_to_items=claim_state.chunk_to_items,
                )

                doc_thread_id = str(uuid.uuid4())

                await doc_processing_app.aupdate_state(
                    {"configurable": {"thread_id": doc_thread_id}},
                    doc_processing_state.model_dump(),
                )

                new_records.append(
                    {
                        "id": uuid.uuid4(),
                        "project_id": workflow.project_id,
                        "type": "document_processing",
                        "status": "COMPLETED",
                        "langgraph_thread_id": doc_thread_id,
                        "created_at": workflow.created_at,
                        "last_updated_at": workflow.created_at,
                    }
                )

                logger.info(
                    f"Prepared migration for workflow {workflow.id} -> thread {doc_thread_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to migrate workflow {workflow.id}: {e}", exc_info=True
                )
                continue

    if new_records:
        connection.execute(workflow_runs.insert(), new_records)
        connection.commit()
        logger.info(f"Migration complete: {len(new_records)} workflows migrated")
    else:
        logger.info("Migration complete: 0 workflows migrated")
