# Workflow runs

A map of a run's life, from the API call to its end, and the file and function that own each step. How a skill declares a workflow is in [skill-workflows.md](./skill-workflows.md).

```
POST /start ─► start_or_join_run ─► PENDING ─┬─► AWAITING_APPROVAL (gate) ─► approve ─┐
                                             │◄──────────────────────────────────────┘
               promote_ready_runs ─► job queued ─► claim_run ─► RUNNING ─► COMPLETED | FAILED | CANCELLED
```

## Three similar names

- `lib/api/services/workflow_runner.py`: the API side. Checks the caller, creates or joins the runs, then calls `promote_ready_runs`. Runs nothing.
- `lib/workflows/runner.py`: the execution side. Runs one claimed run's LangGraph graph and writes its result.
- `lib/services/workflow_runs/`: the run rows and the rules between the two (start, promote, queue jobs, gates, reaper).

## Statuses

`WorkflowRunStatus` in `lib/models/workflow_run.py`. Waiting: PENDING, AWAITING_APPROVAL (`WAITING_WORKFLOW_RUN_STATUSES`). Active: waiting plus RUNNING (`ACTIVE_WORKFLOW_RUN_STATUSES`). Terminal: COMPLETED, CANCELLED, FAILED (`TERMINAL_WORKFLOW_RUN_STATUSES`). Terminal is write-once: `update_workflow_run_status` in `service.py` never overwrites it. Python and the API use the lowercase values (`"running"`); the Postgres enum stores the member names (`'RUNNING'`), so raw SQL uses uppercase. A FAILED run has a `failure_reason` (`WorkflowRunFailureReason`).

## A run, step by step

1. **API entry.** `lib/api/routers/workflows.py` (`/api/workflows/start`, `/start-multiple`), the Review Assistant router and the MCP tool call `start_workflow_run`, `start_multiple_workflow_runs` or `run_multiple_workflows_blocking` in `lib/api/services/workflow_runner.py`. Access and API-key checks are in `workflow_start_checks.py`. A batch resolves dependencies and gates in `plan_batch` (`workflow_batch.py`).
2. **Create or join.** `start_or_join_run` (`lib/services/workflow_runs/start.py`) inserts a PENDING run with `ON CONFLICT DO NOTHING`, or joins the run of that type already waiting. It stores the config (without the API key) and the starting user on the row.
3. **One running, one waiting per type.** Per project, revision and type the database allows one RUNNING run and one waiting run: the partial unique indexes `uq_workflow_runs_one_running` and `uq_workflow_runs_one_waiting` on `WorkflowRun`. Manifests with `independent_runs` are exempt.
4. **Promote.** `promote_ready_runs` (`promoter.py`) is the only thing that decides what runs. It is called after every start, gate approval, run end, cancel, reaper fail and new revision (`create_new_revision` in `lib/services/projects/service.py`). It takes an advisory lock per project revision and applies `plan_promotion` (`promotion_plan.py`, pure, no I/O). A waiting run is:
   - cancelled when a required dependency last ended CANCELLED or FAILED or never ran (cascades);
   - blocked while a required dependency is not COMPLETED, an optional one is active, or a run of its type is RUNNING;
   - parked in AWAITING_APPROVAL when an unapproved gate is all that holds it back;
   - otherwise ready: its job is queued.
5. **Gates.** `gates.py`: `get_effective_gates` (own gates plus those of required dependencies) and `approve_gate`. `approve_project_gate` in `workflow_runner.py` approves, then promotes, which releases parked runs to PENDING.
6. **Queue.** `lib/services/workflow_runs/jobs.py`: `defer_run_job` queues a Procrastinate job (task `run_workflow` in `lib/services/task_queue/tasks.py`). Its `queueing_lock` is the run id; its `lock` (`run_job_lock`) is project, revision and type, so two runs of a type never execute together. Each API process runs a queue worker (`run_task_queue_worker` in `lib/config/task_queue.py`, started from the lifespan in `lib/api/main.py`).
7. **Running.** The `run_workflow` task calls `claim_run`, which moves PENDING to RUNNING and sets `started_at`; it returns None (job does nothing) if the run is no longer PENDING. Then `execute_claimed_run` and `run_workflow_from_config` in `lib/workflows/runner.py` rebuild the config from the row, read the prior same-type run's final state (`get_latest_workflow_run_state_by_type`, passed to `create_state` as `prior_self_state`, so accumulating workflows build on it), and stream the graph in `run_workflow`. State is saved after every chunk (`persist_workflow_run_state`).
8. **Supervision and heartbeat.** `heartbeat_while_preparing` (`heartbeat.py`) beats while the state is built. Then every node runs under `register_node` (`lib/workflows/decorators.py`): `_supervise_node` writes `heartbeat_at` every `CANCELLATION_CHECK_INTERVAL` (5 s) and cancels the node once the run's status is terminal.
9. **Ends.** `run_workflow` writes COMPLETED (node errors stay in `state.errors`), FAILED with TIMEOUT after the manifest's `max_duration_seconds`, or FAILED with UNHANDLED_EXCEPTION. The task then calls `promote_ready_runs` while it still holds the type's lock.
10. **Cancel.** `cancel_workflow_run_endpoint` (router) calls `cancel_run` (`promoter.py`): mark CANCELLED (`cancel_workflow_run` in `service.py`), drop the job if still queued (`cancel_queued_job`), then promote, which cancels waiting required-dependents. A RUNNING run stops when its node supervisor sees CANCELLED; the runner then calls the manifest's `on_cancel` (also used after a timeout) to clean up state.
11. **Reaper.** `reaper.py`, started from the lifespan: every 30 s `_reap_once_locked` fails a RUNNING run with no heartbeat for `REAPER_GRACE_SECONDS` (60 s) and a PENDING run untouched for `PENDING_GRACE_SECONDS` (2 h), both with reason NO_HEARTBEAT, runs `on_cancel` on the state, then promotes. It also frees the jobs a dead worker left behind (`release_stalled_run_jobs` in `jobs.py`).

## Manifests

Each workflow has `lib/workflows/<name>/manifest.py`, a `WorkflowManifest` subclass (`lib/workflows/manifest.py`), registered in `lib/workflows/registry.py` (`get_workflow_manifest`, `create_graph`, `create_state`). Fields that shape the lifecycle: `required_dependencies`, `optional_dependencies`, `gates`, `independent_runs`, `always_run`, `max_duration_seconds`, `max_concurrency`, `auto_rerun_on_new_revision` and the `on_cancel` hook. Skill-declared workflows get their manifest from `lib/workflows/skill_workflows.py`.

## Which file for

- Why a run is still PENDING: `plan_promotion` in `promotion_plan.py`.
- Run rows, status writes, state reads: `lib/services/workflow_runs/service.py`.
- Node progress shown in the UI: `progress.py`. Who may read a run: `access.py`.
- Dependency order of a batch: `lib/workflows/dependency_resolver.py`.
