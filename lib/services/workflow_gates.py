"""Consent gates that park workflow runs until a user approves them.

A gate is a consent the user gives once per project revision (see
``WorkflowGate``). Manifests declare the gates they need; a workflow also
inherits the gates of everything it required-depends on, so a dependent of a
gated workflow waits alongside it instead of failing to find its dependency.

Nothing waits in-process on such a run: the row sits in AWAITING_APPROVAL
until ``approve_gate`` writes the approval and ``release_runs_awaiting_approval`` moves
every run whose gates are now all satisfied back to PENDING for scheduling.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Set

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.workflow_gate_approval import WorkflowGateApproval
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.workflows.models import WorkflowGate, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)


def get_effective_gates(workflow_type: WorkflowRunType) -> List[WorkflowGate]:
    """The workflow's own gates plus those of its required dependencies, transitively.

    Order is stable (own gates first, then dependencies in declaration order)
    and each gate appears once.
    """
    seen: Set[WorkflowGate] = set()
    ordered: List[WorkflowGate] = []
    visited: Set[WorkflowRunType] = set()

    def visit(current: WorkflowRunType) -> None:
        if current in visited:
            return
        visited.add(current)
        manifest = get_workflow_manifest(current)
        for gate in manifest.gates:
            if gate not in seen:
                seen.add(gate)
                ordered.append(gate)
        for dep in manifest.required_dependencies:
            visit(dep)

    visit(workflow_type)
    return ordered


async def get_approved_gates(project_id: str, revision: int) -> Set[WorkflowGate]:
    """Gates already approved for this project revision."""
    async with get_async_db_session() as session:
        stmt = select(col(WorkflowGateApproval.gate)).where(
            and_(
                col(WorkflowGateApproval.project_id) == project_id,
                col(WorkflowGateApproval.revision) == revision,
            )
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {WorkflowGate(row) for row in rows}


async def get_unsatisfied_gates(
    project_id: str, revision: int, workflow_type: WorkflowRunType
) -> List[WorkflowGate]:
    """Gates that still block ``workflow_type`` in this project revision."""
    approved = await get_approved_gates(project_id, revision)
    return [g for g in get_effective_gates(workflow_type) if g not in approved]


async def approve_gate(
    project_id: str,
    revision: int,
    gate: WorkflowGate,
    approved_by_user_id: Optional[uuid.UUID] = None,
) -> None:
    """Record the approval. Idempotent: a second approval leaves the first row as is."""
    async with get_async_db_session() as session:
        stmt = (
            pg_insert(WorkflowGateApproval)
            .values(
                id=uuid.uuid4(),
                project_id=project_id,
                revision=revision,
                gate=gate.value,
                approved_at=datetime.utcnow(),
                approved_by_user_id=approved_by_user_id,
            )
            .on_conflict_do_nothing(
                constraint="uq_workflow_gate_approvals_project_revision_gate"
            )
        )
        await session.execute(stmt)
        await session.commit()
    logger.info(
        f"Gate {gate.value} approved for project {project_id} revision {revision}"
    )


async def get_runs_awaiting_approval(
    project_id: str, revision: int
) -> List[WorkflowRun]:
    """Runs of this project revision sitting in AWAITING_APPROVAL."""
    async with get_async_db_session() as session:
        stmt = (
            select(WorkflowRun)
            .where(
                and_(
                    col(WorkflowRun.project_id) == project_id,
                    col(WorkflowRun.revision) == revision,
                    col(WorkflowRun.status) == WorkflowRunStatus.AWAITING_APPROVAL,
                )
            )
            .order_by(col(WorkflowRun.created_at).asc())
        )
        return list((await session.execute(stmt)).scalars().all())


async def release_runs_awaiting_approval(
    project_id: str, revision: int
) -> List[WorkflowRun]:
    """Move every run awaiting approval whose gates are all satisfied to PENDING.

    Returns the released runs so the caller can schedule them. Runs still
    blocked by another gate keep waiting.
    """
    approved = await get_approved_gates(project_id, revision)
    released: List[WorkflowRun] = []
    for run in await get_runs_awaiting_approval(project_id, revision):
        if not _gates_satisfied(run.type, approved):
            continue
        async with get_async_db_session() as session:
            stmt = (
                update(WorkflowRun)
                .where(
                    and_(
                        col(WorkflowRun.id) == run.id,
                        # Only release a run that is still waiting; a concurrent
                        # cancel must win.
                        col(WorkflowRun.status) == WorkflowRunStatus.AWAITING_APPROVAL,
                    )
                )
                .values(status=WorkflowRunStatus.PENDING)
            )
            result = await session.execute(stmt)
            await session.commit()
        if result.rowcount:  # type: ignore[attr-defined]  # CursorResult exposes rowcount at runtime
            run.status = WorkflowRunStatus.PENDING
            released.append(run)
    if released:
        logger.info(
            f"Released {len(released)} runs awaiting approval for project {project_id} "
            f"revision {revision}: {[r.type for r in released]}"
        )
    return released


def _gates_satisfied(
    workflow_type: WorkflowRunType | str, approved: Set[WorkflowGate]
) -> bool:
    # Rows outlive workflows: a retired slug may not even be an enum member any
    # more. Such a run has nothing left to start, so leave it waiting rather
    # than schedule something that cannot run.
    try:
        resolved = WorkflowRunType(workflow_type)
    except ValueError:
        return False
    if get_workflow_manifest(resolved, raise_exception=False) is None:
        return False
    return all(g in approved for g in get_effective_gates(resolved))
