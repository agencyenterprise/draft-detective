"""Create a workflow run, or join the one already waiting.

Per project, revision and type the database holds at most one RUNNING run and
at most one waiting run (PENDING or AWAITING_APPROVAL); workflows whose
manifest sets ``independent_runs`` are exempt (see the unique indexes on
``WorkflowRun``). A start inserts its run PENDING with ``ON CONFLICT DO
NOTHING``; when a waiting run already holds the slot, the start joins it and
creates nothing. So a start while a run is RUNNING queues one run behind it,
and every later start joins that one.

A start never schedules anything: ``promote_ready_runs`` decides when a
waiting run runs, and whether it waits on a gate.
"""

import logging
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.workflow_run import (
    WAITING_WORKFLOW_RUN_STATUSES,
    WorkflowRun,
    WorkflowRunStatus,
)
from lib.workflows.models import BaseWorkflowConfig, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# Each attempt either creates or joins a run, unless the waiting run left its
# slot (started or cancelled) in between; a few cover any real race.
MAX_START_ATTEMPTS = 5

# Never stored on the run: the job resolves the key when the run starts.
_SECRET_CONFIG_FIELDS = {"openai_api_key"}


class RunStart(BaseModel):
    """The waiting run that serves a start."""

    run_id: str
    status: WorkflowRunStatus
    created: bool


async def start_or_join_run(
    config: BaseWorkflowConfig,
    workflow_type: WorkflowRunType,
    revision: int,
    *,
    started_by: uuid.UUID | None,
) -> RunStart:
    """Create the PENDING run of this type, or join the waiting one.

    A created run stores ``config`` (without its API key) and ``started_by``
    for the job that runs it; a joined run keeps those it was created with.
    """
    for _ in range(MAX_START_ATTEMPTS):
        created = await _insert_waiting_run(config, workflow_type, revision, started_by)
        if created is not None:
            return RunStart(run_id=str(created.id), status=created.status, created=True)
        waiting = await get_waiting_run(config.project_id, workflow_type, revision)
        if waiting is not None:
            logger.info(f"Joined waiting {waiting.type} run {waiting.id}")
            return RunStart(
                run_id=str(waiting.id), status=waiting.status, created=False
            )
    raise RuntimeError(
        f"Could not create or join a {workflow_type.value} run for project "
        f"{config.project_id} revision {revision}"
    )


async def _insert_waiting_run(
    config: BaseWorkflowConfig,
    workflow_type: WorkflowRunType,
    revision: int,
    started_by: uuid.UUID | None,
) -> WorkflowRun | None:
    """Insert the run, or return None when a waiting run already holds the slot.

    Each run gets a fresh thread id; accumulating workflows carry prior state
    forward via prior_self_state (read at execution time in the runner)
    instead of thread reuse.
    """
    stmt = (
        pg_insert(WorkflowRun)
        .values(
            id=uuid.uuid4(),
            project_id=uuid.UUID(config.project_id),
            type=workflow_type.value,
            langgraph_thread_id=str(uuid.uuid4()),
            status=WorkflowRunStatus.PENDING,
            revision=revision,
            model=config.model,
            config_json=config.model_dump(mode="json", exclude=_SECRET_CONFIG_FIELDS),
            started_by_user_id=started_by,
            independent_run=get_workflow_manifest(workflow_type).independent_runs,
        )
        .on_conflict_do_nothing()
        .returning(WorkflowRun)
    )
    async with get_async_db_session() as session:
        run = (await session.execute(stmt)).scalar_one_or_none()
        await session.commit()
    return run


async def get_waiting_run(
    project_id: str, workflow_type: WorkflowRunType, revision: int
) -> WorkflowRun | None:
    """The run of this type waiting to start on the revision, if any."""
    stmt = select(WorkflowRun).where(
        col(WorkflowRun.project_id) == project_id,
        col(WorkflowRun.type) == workflow_type,
        col(WorkflowRun.revision) == revision,
        col(WorkflowRun.status).in_(WAITING_WORKFLOW_RUN_STATUSES),
        col(WorkflowRun.independent_run).is_(False),
    )
    async with get_async_db_session() as session:
        return (await session.execute(stmt)).scalar_one_or_none()
