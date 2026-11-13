"""Consent gates that park workflow runs until a user approves them.

A gate is a consent the user gives once per project revision (see
``WorkflowGate``). Manifests declare the gates they need; a workflow also
inherits the gates of everything it required-depends on, so a dependent of a
gated workflow waits alongside it instead of failing to find its dependency.

Nothing waits in-process on such a run: ``promote_ready_runs`` parks it in
AWAITING_APPROVAL once the gate is all that holds it back, and moves it back to
PENDING (and queues it) on the pass after ``approve_gate`` writes the approval.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import and_, col

from lib.config.database import get_async_db_session
from lib.models.workflow_gate_approval import WorkflowGateApproval
from lib.workflows.models import WorkflowGate, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)


def get_effective_gates(workflow_type: WorkflowRunType) -> list[WorkflowGate]:
    """The workflow's own gates plus those of its required dependencies, transitively.

    Order is stable (own gates first, then dependencies in declaration order)
    and each gate appears once.
    """
    seen: set[WorkflowGate] = set()
    ordered: list[WorkflowGate] = []
    visited: set[WorkflowRunType] = set()

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


async def get_approved_gates(project_id: str, revision: int) -> set[WorkflowGate]:
    """Gates already approved for this project revision.

    The column is a plain string, so a value written by a gate that has since
    been renamed or retired is skipped rather than allowed to break every
    workflow start for the revision.
    """
    async with get_async_db_session() as session:
        stmt = select(col(WorkflowGateApproval.gate)).where(
            and_(
                col(WorkflowGateApproval.project_id) == project_id,
                col(WorkflowGateApproval.revision) == revision,
            )
        )
        rows = (await session.execute(stmt)).scalars().all()
    approved: set[WorkflowGate] = set()
    for row in rows:
        try:
            approved.add(WorkflowGate(row))
        except ValueError:
            logger.warning(
                f"Ignoring unknown gate {row!r} approved for project {project_id} "
                f"revision {revision}"
            )
    return approved


async def get_unsatisfied_gates(
    project_id: str, revision: int, workflow_type: WorkflowRunType
) -> list[WorkflowGate]:
    """Gates that still block ``workflow_type`` in this project revision."""
    approved = await get_approved_gates(project_id, revision)
    return [g for g in get_effective_gates(workflow_type) if g not in approved]


async def approve_gate(
    project_id: str,
    revision: int,
    gate: WorkflowGate,
    approved_by_user_id: uuid.UUID | None = None,
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
