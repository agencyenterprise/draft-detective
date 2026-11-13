"""The promoter's rules, on runs built in memory (see promotion_plan)."""

import uuid
from datetime import datetime, timedelta

from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunType
from lib.services.workflow_runs.promotion_plan import PromotionPlan, plan_promotion
from lib.workflows.models import WorkflowGate

PROJECT = uuid.uuid4()
DOCS = WorkflowRunType.DOCUMENT_PROCESSING
SUMMARY = WorkflowRunType.DOCUMENT_SUMMARIZATION
EXTRACTION = WorkflowRunType.REFERENCE_EXTRACTION
MATCHING = WorkflowRunType.REFERENCE_FILE_MATCHING
DOWNLOADER = WorkflowRunType.REFERENCE_DOWNLOADER
FIGURES = WorkflowRunType.FIGURES_TABLES_CHECK
CLAIM = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
ASSISTANT = WorkflowRunType.REVIEW_ASSISTANT
REVIEW = {WorkflowGate.REFERENCE_REVIEW}

_clock = datetime(2026, 11, 13)


def _run(
    workflow_type: WorkflowRunType | str, status: WorkflowRunStatus
) -> WorkflowRun:
    global _clock
    _clock += timedelta(seconds=1)
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=PROJECT,
        type=workflow_type,
        langgraph_thread_id=str(uuid.uuid4()),
        status=status,
        revision=1,
        created_at=_clock,
        independent_run=workflow_type == ASSISTANT,
    )


def _ids(runs: list[WorkflowRun]) -> set[uuid.UUID]:
    return {run.id for run in runs}


def _plan(
    *runs: WorkflowRun, approved: set[WorkflowGate] | None = None
) -> PromotionPlan:
    return plan_promotion(list(runs), approved or set())


def _claim_prerequisites_completed() -> list[WorkflowRun]:
    return [
        _run(workflow_type, WorkflowRunStatus.COMPLETED)
        for workflow_type in (DOCS, SUMMARY, EXTRACTION, MATCHING)
    ]


def test_a_run_waits_until_its_required_dependency_completes():
    docs = _run(DOCS, WorkflowRunStatus.PENDING)
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    assert _ids(_plan(docs, figures).ready) == {docs.id}

    docs.status = WorkflowRunStatus.COMPLETED
    assert _ids(_plan(docs, figures).ready) == {figures.id}


def test_the_latest_ended_run_of_a_dependency_counts_when_none_is_active():
    failed = _run(DOCS, WorkflowRunStatus.FAILED)
    completed = _run(DOCS, WorkflowRunStatus.COMPLETED)
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    assert _ids(_plan(failed, completed, figures).ready) == {figures.id}


def test_a_dependency_rerun_holds_the_dependent_back_again():
    completed = _run(DOCS, WorkflowRunStatus.COMPLETED)
    rerun = _run(DOCS, WorkflowRunStatus.RUNNING)
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    assert _plan(completed, rerun, figures).ready == []


def test_a_run_waits_while_a_run_of_its_type_is_running():
    running = _run(FIGURES, WorkflowRunStatus.RUNNING)
    waiting = _run(FIGURES, WorkflowRunStatus.PENDING)
    docs = _run(DOCS, WorkflowRunStatus.COMPLETED)

    assert _plan(docs, running, waiting).ready == []

    running.status = WorkflowRunStatus.CANCELLED
    assert _ids(_plan(docs, running, waiting).ready) == {waiting.id}


def test_independent_runs_go_side_by_side():
    running = _run(ASSISTANT, WorkflowRunStatus.RUNNING)
    first = _run(ASSISTANT, WorkflowRunStatus.PENDING)
    second = _run(ASSISTANT, WorkflowRunStatus.PENDING)

    assert _ids(_plan(running, first, second).ready) == {first.id, second.id}


def test_an_active_optional_dependency_holds_the_run_back():
    downloader = _run(DOWNLOADER, WorkflowRunStatus.RUNNING)
    claim = _run(CLAIM, WorkflowRunStatus.PENDING)
    runs = [*_claim_prerequisites_completed(), downloader, claim]

    assert plan_promotion(runs, REVIEW).ready == []

    downloader.status = WorkflowRunStatus.FAILED
    assert _ids(plan_promotion(runs, REVIEW).ready) == {claim.id}


def test_a_gate_parks_the_run_only_once_it_is_the_last_blocker():
    matching = _run(MATCHING, WorkflowRunStatus.RUNNING)
    claim = _run(CLAIM, WorkflowRunStatus.PENDING)
    others = [_run(t, WorkflowRunStatus.COMPLETED) for t in (DOCS, SUMMARY, EXTRACTION)]

    plan = _plan(*others, matching, claim)
    assert plan.park == [] and plan.ready == []

    matching.status = WorkflowRunStatus.COMPLETED
    plan = _plan(*others, matching, claim)
    assert _ids(plan.park) == {claim.id}
    assert plan.ready == []


def test_an_approved_gate_releases_the_parked_run_and_queues_it():
    claim = _run(CLAIM, WorkflowRunStatus.AWAITING_APPROVAL)

    plan = _plan(*_claim_prerequisites_completed(), claim, approved=REVIEW)

    assert _ids(plan.release) == {claim.id}
    assert _ids(plan.ready) == {claim.id}


def test_a_parked_run_goes_back_to_pending_when_another_blocker_appears():
    prerequisites = _claim_prerequisites_completed()
    rerun = _run(MATCHING, WorkflowRunStatus.PENDING)
    claim = _run(CLAIM, WorkflowRunStatus.AWAITING_APPROVAL)

    plan = _plan(*prerequisites, rerun, claim)

    assert _ids(plan.release) == {claim.id}
    assert claim.id not in _ids(plan.ready)


def test_a_failed_dependency_cancels_waiting_dependents_transitively():
    extraction = _run(EXTRACTION, WorkflowRunStatus.FAILED)
    docs = _run(DOCS, WorkflowRunStatus.COMPLETED)
    summary = _run(SUMMARY, WorkflowRunStatus.COMPLETED)
    matching = _run(MATCHING, WorkflowRunStatus.PENDING)
    claim = _run(CLAIM, WorkflowRunStatus.PENDING)
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    plan = _plan(extraction, docs, summary, matching, claim, figures)

    assert _ids(plan.cancel) == {matching.id, claim.id}
    assert _ids(plan.ready) == {figures.id}


def test_a_cancelled_dependency_cancels_a_parked_dependent():
    prerequisites = _claim_prerequisites_completed()
    cancelled = _run(MATCHING, WorkflowRunStatus.CANCELLED)
    claim = _run(CLAIM, WorkflowRunStatus.AWAITING_APPROVAL)

    assert _ids(_plan(*prerequisites, cancelled, claim).cancel) == {claim.id}


def test_a_required_dependency_that_never_ran_cancels_the_run():
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    assert _ids(_plan(figures).cancel) == {figures.id}


def test_a_lost_dependency_with_a_waiting_rerun_holds_the_dependent_instead():
    failed = _run(DOCS, WorkflowRunStatus.FAILED)
    rerun = _run(DOCS, WorkflowRunStatus.PENDING)
    figures = _run(FIGURES, WorkflowRunStatus.PENDING)

    plan = _plan(failed, rerun, figures)

    assert plan.cancel == []
    assert _ids(plan.ready) == {rerun.id}


def test_running_and_ended_runs_are_left_alone():
    running = _run(FIGURES, WorkflowRunStatus.RUNNING)
    failed_dependency = _run(DOCS, WorkflowRunStatus.FAILED)

    assert _plan(running, failed_dependency) == PromotionPlan()


def test_a_retired_workflow_is_left_alone():
    retired = _run("retired_workflow", WorkflowRunStatus.PENDING)

    assert _plan(retired) == PromotionPlan()
