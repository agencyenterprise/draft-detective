# Workflow runs

A map of a run's life, from the API call to its end, and the file and function that own each step. How a skill declares a workflow is in [skill-workflows.md](./skill-workflows.md).

```
POST /start ─► start_or_join_run ─► PENDING ──────────────────────► background task
                                └─► AWAITING_APPROVAL ─► approve ─┘        │
  wait_for_dependencies (dependencies, then claim the same-type queue) ◄───┘
      ─► RUNNING ─► run_workflow ─► COMPLETED | FAILED | CANCELLED
```

## Three similar names

- `lib/api/services/workflow_runner.py`: the API side. Checks the caller, creates or joins the runs and schedules them as FastAPI background tasks.
- `lib/workflows/runner.py`: the execution side. Waits for a run's turn, then runs its LangGraph graph and writes the result.
- `lib/services/workflow_runs/`: the run rows and the rules between the two (start, waiting, same-type queue, gates, reaper).

## Statuses

`WorkflowRunStatus` in `lib/models/workflow_run.py`. Waiting: PENDING, AWAITING_APPROVAL (`WAITING_WORKFLOW_RUN_STATUSES`). Active: waiting plus RUNNING (`ACTIVE_WORKFLOW_RUN_STATUSES`). Terminal: COMPLETED, CANCELLED, FAILED (`TERMINAL_WORKFLOW_RUN_STATUSES`). Terminal is write-once: `update_workflow_run_status` in `service.py` never overwrites it. Python and the API use the lowercase values (`"running"`); the Postgres enum stores the member names (`'RUNNING'`), so raw SQL uses uppercase. A FAILED run has a `failure_reason` (`WorkflowRunFailureReason`).

## A run, step by step

1. **API entry.** `lib/api/routers/workflows.py` (`/api/workflows/start`, `/start-multiple`), the Review Assistant router and the MCP tool call `start_workflow_run`, `start_multiple_workflow_runs` or `run_multiple_workflows_blocking` in `lib/api/services/workflow_runner.py`. A batch resolves dependencies, skips reusable ones (`_reused_dependency_run`) and checks gates in `_prepare_workflow_items`.
2. **Create or join.** `start_or_join_run` (`lib/services/workflow_runs/start.py`) inserts the run with `ON CONFLICT DO NOTHING`, PENDING, or AWAITING_APPROVAL when a gate is unsatisfied. When a run of the type is already waiting, the start joins it. `RunStart.schedule` says whether this caller must schedule the run: each waiting run is scheduled exactly once.
3. **One running, one waiting per type.** Per project, revision and type the database allows one RUNNING run and one waiting run: the partial unique indexes `uq_workflow_runs_one_running` and `uq_workflow_runs_one_waiting` on `WorkflowRun`. Manifests with `independent_runs` are exempt.
4. **Schedule.** The API side adds `run_workflow_with_dependency_check` (`lib/workflows/runner.py`) as a FastAPI background task, in the process that took the request. A batch runs its items together through `_run_multiple_workflows_concurrently`.
5. **Gates.** `gates.py`: `get_effective_gates` (own gates plus those of required dependencies), `approve_gate` and `release_runs_awaiting_approval`, which moves approved runs back to PENDING. `approve_project_gate` in `workflow_runner.py` approves, releases and schedules them.
6. **Wait.** `wait_for_dependencies` (`lib/services/workflow_runs/orchestration.py`) polls every 5 s until no required or optional dependency is active. A required dependency that ended CANCELLED or FAILED cancels the run; one with no run at all raises `ValueError`. It also stops if the run itself ended meanwhile, and gives up after `DEPENDENCY_WAIT_TIMEOUT` (2 h, FAILED with DEPENDENCY_TIMEOUT).
7. **Same-type queue and RUNNING.** Unless the workflow has `independent_runs`, the wait ends with `claim_same_type_queue_head` (`queue.py`): under an advisory lock per project, type and revision, a run with nothing RUNNING or older PENDING ahead of it moves PENDING to RUNNING. Runs of a type go first come, first served. An independent run is marked RUNNING by `run_workflow` instead.
8. **Running.** `run_workflow_from_config` (`lib/workflows/runner.py`) reads the prior same-type run's final state (`get_latest_workflow_run_state_by_type`, passed to `create_state` as `prior_self_state`, so accumulating workflows build on it), builds the state, then `run_workflow` streams the graph and saves the state after every chunk (`persist_workflow_run_state`).
9. **Supervision and heartbeat.** `heartbeat_while_preparing` (`queue.py`) beats while the state is built. Then every node runs under `register_node` (`lib/workflows/decorators.py`): `_supervise_node` writes `heartbeat_at` every `CANCELLATION_CHECK_INTERVAL` (5 s) and cancels the node once the run's status is terminal.
10. **Ends.** `run_workflow` writes COMPLETED (node errors stay in `state.errors`), FAILED with TIMEOUT after the manifest's `max_duration_seconds`, or FAILED with UNHANDLED_EXCEPTION. `run_workflow_with_dependency_check` fails the run for errors raised before the graph starts.
11. **Cancel.** `cancel_workflow_run_endpoint` (router) calls `cancel_workflow_run` (`service.py`), which marks the run CANCELLED and cancels its active required-dependents (`_cascade_cancel_dependents`; `fail_workflow_run` cascades the same way). A waiting run's next poll in `wait_for_dependencies` sees the terminal status and stops. A RUNNING run stops when its node supervisor sees it; the runner then calls the manifest's `on_cancel` (also used after a timeout) to clean up state. A new revision cancels the old revision's active runs (`create_new_revision` in `lib/services/projects/service.py`).
12. **Reaper.** `reaper.py`, started from the lifespan in `lib/api/main.py`: every 30 s `_reap_once_locked` fails a RUNNING run with no heartbeat for `REAPER_GRACE_SECONDS` (60 s) and a PENDING run untouched for `PENDING_GRACE_SECONDS` (2 h), both with reason NO_HEARTBEAT, and runs `on_cancel` on the state. This is what recovers runs whose process died: background tasks do not survive a restart.

## Manifests

Each workflow has `lib/workflows/<name>/manifest.py`, a `WorkflowManifest` subclass (`lib/workflows/manifest.py`), registered in `lib/workflows/registry.py` (`get_workflow_manifest`, `create_graph`, `create_state`). Fields that shape the lifecycle: `required_dependencies`, `optional_dependencies`, `gates`, `independent_runs`, `always_run`, `max_duration_seconds`, `max_concurrency`, `auto_rerun_on_new_revision` and the `on_cancel` hook. Skill-declared workflows get their manifest from `lib/workflows/skill_workflows.py`.

## Which file for

- Why a run is still PENDING: `wait_for_dependencies` in `orchestration.py`, then `get_run_ahead_in_same_type_queue` in `queue.py`.
- Run rows, status writes, state reads: `lib/services/workflow_runs/service.py`.
- Node progress shown in the UI: `progress.py`. Who may read a run: `access.py`.
- Dependency order of a batch: `lib/workflows/dependency_resolver.py`.
