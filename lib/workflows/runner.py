import asyncio
import logging
import uuid
from collections.abc import Mapping
from typing import Any, cast

from langfuse import propagate_attributes
from langgraph.channels.base import BaseChannel
from langgraph.graph import StateGraph

from lib.config.database import get_async_db_session
from lib.config.env import config as env_config
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback
from lib.config.llm_models import LLMModel
from lib.models.user import User
from lib.models.workflow_run import (
    WorkflowRun,
    WorkflowRunFailureReason,
    WorkflowRunStatus,
    WorkflowRunType,
)
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issue_persistence import persist_workflow_issues
from lib.services.projects.service import get_project_by_id
from lib.services.users import get_user_decrypted_api_key
from lib.services.vector_store import VectorStoreService
from lib.services.workflow_runs.heartbeat import heartbeat_while_preparing
from lib.services.workflow_runs.service import (
    fail_workflow_run,
    get_latest_workflow_run_state_by_type,
    get_project_workflow_runs,
    persist_workflow_run_state,
    update_workflow_run_status,
)
from lib.workflows.config_factory import create_workflow_config
from lib.workflows.context import ContextSchema
from lib.workflows.error_details import build_workflow_error
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import BaseWorkflowConfig, WorkflowCancelledError
from lib.workflows.registry import (
    create_graph,
    create_state,
    get_config_type,
    get_workflow_manifest,
)
from lib.workflows.state_updates import apply_node_update
from lib.workflows.workflow_types import WorkflowConfig, WorkflowState

logger = logging.getLogger(__name__)


async def execute_claimed_run(run: WorkflowRun) -> None:
    """Run a run its job has just claimed (moved to RUNNING), to its end.

    The config and the user come from the run's row: the config it was started
    with, and the user who started it. ``run_workflow`` records the outcome of
    the graph itself; this records every failure before the graph starts (no
    API key, building the state) as FAILED. A run cancelled meanwhile keeps
    its CANCELLED status.
    """
    workflow_run_id = str(run.id)
    try:
        config = await _config_of(run)
        await run_workflow_from_config(
            config=config,
            thread_id=run.langgraph_thread_id,
            workflow_run_id=workflow_run_id,
            user=await _starter_of(run),
            revision=run.revision,
        )
    except WorkflowCancelledError:
        logger.info(f"Workflow {workflow_run_id} ({run.type}) was cancelled")
    except Exception as e:
        logger.error(f"Error running workflow: {e}", exc_info=True)
        await fail_workflow_run(
            workflow_run_id,
            str(run.project_id),
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            failure_message=str(e),
        )


async def _config_of(run: WorkflowRun) -> WorkflowConfig:
    """The config the run was started with; for a run created before configs
    were stored, the one a start would build from its project."""
    workflow_type = WorkflowRunType(run.type)
    if run.config_json is not None:
        stored = {**run.config_json, "model": run.model}
        return cast(
            WorkflowConfig, get_config_type(workflow_type).model_validate(stored)
        )
    project = await get_project_by_id(str(run.project_id))
    if project is None:
        raise ValueError(f"Project {run.project_id} of run {run.id} no longer exists")
    return create_workflow_config(project, workflow_type, model=run.model)


async def _starter_of(run: WorkflowRun) -> User | None:
    if run.started_by_user_id is None:
        return None
    async with get_async_db_session() as session:
        return await session.get(User, run.started_by_user_id)


async def run_workflow_from_config(
    config: WorkflowConfig,
    thread_id: str,
    workflow_run_id: str,
    user: User | None,
    revision: int,
    seed_prior_state: bool = True,
) -> WorkflowState:
    graph = create_graph(config.type)
    context = create_context(
        config, workflow_run_id=workflow_run_id, user=user, revision=revision
    )

    # Redact the OpenAI API key from the config so it doesn't get saved in the state
    config.openai_api_key = "[REDACTED]"

    # The job claimed the run (it is RUNNING), so it beats while it prepares;
    # graph nodes take over the heartbeat after this.
    async with heartbeat_while_preparing(workflow_run_id):
        # Read the prior same-type run's state here — at execution time, once
        # the promoter let this run go after the previous one — so accumulating workflows seed from the prior run's FINAL state
        # rather than a snapshot taken while it was still running. Exclude this
        # run (its state_json is still NULL now anyway). Skipped on resume
        # (seed_prior_state=False).
        prior_self_state = (
            await get_latest_workflow_run_state_by_type(
                config.project_id,
                config.type,
                revision,
                exclude_run_id=workflow_run_id,
            )
            if seed_prior_state
            else None
        )

        state = await create_state(
            config, revision=revision, prior_self_state=prior_self_state
        )

    with propagate_attributes(user_id=context.user_id):
        return await run_workflow(
            workflow_run_id=workflow_run_id,
            workflow_type=config.type,
            graph=graph,
            state=state,
            context=context,
            thread_id=thread_id,
        )


async def run_workflow(
    workflow_run_id: str,
    workflow_type: WorkflowRunType,
    graph: StateGraph,
    state: WorkflowState,
    context: ContextSchema,
    thread_id: str,
) -> WorkflowState:
    """
    Run a workflow using LangGraph, persisting the state to the database.

    Args:
        workflow_run_id: The ID of the workflow run record
        workflow_type: The type of the workflow
        graph: The LangGraph graph to run
        state: The initial state of the workflow
        context: The context of the workflow
        thread_id: The run's opaque LangGraph thread id (stored on the run record)

    Returns:
        The updated state of the workflow
    """
    project_id = context.project_id

    logger.info(
        f"Starting workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    # Mark as RUNNING
    await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.RUNNING)

    error_logging_callback = ErrorLoggingCallback(
        workflow_run_id=workflow_run_id,
        project_id=project_id,
    )

    manifest = get_workflow_manifest(workflow_type, raise_exception=False)
    max_duration = manifest.max_duration_seconds if manifest else 1 * 60 * 60

    # Workflows that fan out heavy per-item LLM calls can pin a lower
    # concurrency than the global default to stay under provider rate limits.
    max_concurrency = (
        manifest.max_concurrency if manifest else env_config.LANGGRAPH_MAX_CONCURRENCY
    )

    app = graph.compile().with_config(
        {
            "run_name": f"{workflow_type.value}",
            "callbacks": [langfuse_handler, error_logging_callback],
            "metadata": {"langfuse_session_id": project_id},
            "max_concurrency": max_concurrency,
        }
    )

    updated_state = state.model_copy(deep=True, update={"errors": []})

    try:
        async with asyncio.timeout(max_duration):
            async for mode, chunk in app.astream(  # type: ignore[call-overload]
                updated_state,
                stream_mode=["values", "updates"],
                context=context,
            ):
                updated_state = _merge_stream_chunk(
                    updated_state, mode, chunk, graph.channels
                )
                # state_json is the single source of truth: snapshot the
                # accumulated state after every superstep and every task
                # completion, so fan-out workflows show partial results.
                await persist_workflow_run_state(
                    workflow_run_id, updated_state, unless_failed=True
                )

        # Persist issues after workflow completion. Per-node errors collected
        # in updated_state.errors stay surfaced through state — the run still
        # transitions to COMPLETED ("completed with errors") below.
        await _persist_issues_from_state(
            workflow_run_id=workflow_run_id,
            project_id=project_id,
            workflow_type=workflow_type,
            state=updated_state,
            # The LangGraph checkpointer is retired; no checkpoint id to record.
            checkpoint_id=None,
            revision=context.revision,
        )

        await update_workflow_run_status(workflow_run_id, WorkflowRunStatus.COMPLETED)

    except WorkflowCancelledError:
        logger.info(
            f"Workflow {workflow_type} for project {project_id} was cancelled — running cleanup"
        )
        updated_state = await _run_on_cancel_hook(
            manifest, workflow_run_id, updated_state
        )
        # Status is already CANCELLED in DB; update_workflow_run_status never
        # overwrites a terminal status.

    except TimeoutError:
        logger.error(
            f"Workflow {workflow_type} for project {project_id} exceeded "
            f"max_duration={max_duration}s — marking FAILED"
        )
        # on_cancel is the right place for abnormal-teardown cleanup
        # (per-item statuses stuck in 'pending' would remain otherwise).
        updated_state = await _run_on_cancel_hook(
            manifest, workflow_run_id, updated_state, unless_failed=True
        )
        await fail_workflow_run(
            workflow_run_id,
            project_id,
            failure_reason=WorkflowRunFailureReason.TIMEOUT,
            failure_message=f"Exceeded max_duration of {max_duration}s",
        )

    except Exception as e:
        logger.error(f"Error running workflow {workflow_type}: {e}", exc_info=True)
        error = build_workflow_error(
            task_name="global",
            exc=e,
            workflow_run_id=workflow_run_id,
        )

        # Persist the error onto state_json so the reader path surfaces it in
        # the workflow state for debugging.
        updated_state = updated_state.model_copy(
            update={"errors": [*updated_state.errors, error]}
        )
        # A run the reaper already failed lands here too (its nodes are
        # cancelled as NodeCancelledError): keep the reaper's cleaned state.
        await persist_workflow_run_state(
            workflow_run_id, updated_state, unless_failed=True
        )
        await fail_workflow_run(
            workflow_run_id,
            project_id,
            failure_reason=WorkflowRunFailureReason.UNHANDLED_EXCEPTION,
            failure_message=str(e),
        )

    logger.info(
        f"Completed workflow {workflow_type} for project {project_id} with thread {thread_id}"
    )

    return updated_state


async def _run_on_cancel_hook(
    manifest: WorkflowManifest | None,
    workflow_run_id: str,
    state: WorkflowState,
    *,
    unless_failed: bool = False,
) -> WorkflowState:
    """Best-effort cleanup on cancel or timeout: run on_cancel and persist its state.

    A timeout passes `unless_failed`: a run the reaper already failed keeps the
    reaper's cleaned state. A user cancel is the runner's own to clean up.

    A failing hook or persist is logged and never propagated, so the caller
    still records the run's real outcome (CANCELLED stays, a timeout becomes
    FAILED with reason TIMEOUT). Returns the cleaned state, or ``state``
    unchanged when there is no manifest or the hook itself fails.
    """
    if manifest is None:
        return state
    cleaned = state
    try:
        cleaned = await manifest.on_cancel(state)
        await persist_workflow_run_state(
            workflow_run_id, cleaned, unless_failed=unless_failed
        )
    except Exception as e:
        logger.error(
            f"on_cancel cleanup failed for workflow run {workflow_run_id}: {e}",
            exc_info=True,
        )
    return cleaned


def _merge_stream_chunk(
    state: WorkflowState,
    mode: str,
    chunk: Any,
    channels: Mapping[str, BaseChannel],
) -> WorkflowState:
    """Fold one ``astream`` chunk into the accumulated state.

    ``"values"`` chunks are the full state at a superstep boundary and replace
    it. ``"updates"`` chunks (``{node_name: node_return}``) arrive as each task
    finishes — including each ``Send`` fan-out task mid-superstep — and are
    folded in through the graph's state channels. The next ``"values"`` chunk then
    supersedes them, so the reducer replay never double-counts.
    """
    if mode == "values":
        return state.model_copy(update=chunk)
    for node_update in chunk.values():
        # Nodes may return None (no-op) and interrupts arrive as tuples.
        if isinstance(node_update, dict):
            state = apply_node_update(state, node_update, channels)
    return state


def create_context(
    config: BaseWorkflowConfig,
    revision: int,
    workflow_run_id: str | None = None,
    user: User | None = None,
) -> ContextSchema:
    """
    Create workflow context.

    Key resolution: per-request key > user's stored key > server env var.
    Each workflow's config class declares whether it requires an API key via requires_api_key().
    Workflows that don't use LLMs (data manipulation only) can return False.
    """
    user_stored_key = get_user_decrypted_api_key(user) if user else None
    openai_api_key = (
        config.openai_api_key or user_stored_key or env_config.OPENAI_API_KEY
    )

    if not openai_api_key and config.requires_api_key():
        raise ValueError("No OpenAI API key found in config or environment variables")

    # Only initialize vector store if we have an API key (needed for embeddings)
    vector_store = (
        VectorStoreService(
            openai_api_key,
            workflow_run_id=workflow_run_id,
            project_id=config.project_id,
        )
        if openai_api_key
        else None
    )

    file_artifacts_service = FileArtifactsService(config.project_id, revision=revision)

    return ContextSchema(
        openai_api_key=openai_api_key,
        vector_store=vector_store,
        user_id=str(user.id) if user else None,
        project_id=config.project_id,
        workflow_run_id=workflow_run_id,
        file_artifacts_service=file_artifacts_service,
        revision=revision,
        model_override=LLMModel.from_model_name(config.model) if config.model else None,
    )


async def _persist_issues_from_state(
    workflow_run_id: str,
    project_id: str,
    workflow_type: WorkflowRunType,
    state: WorkflowState,
    checkpoint_id: str | None,
    revision: int = 1,
) -> None:
    """
    Persist issues from workflow state to the database.

    Uses the workflow manifest to convert state to issues.
    Loads all existing workflow states for the project so manifests that
    depend on other workflow states (e.g. reference_validation_v2 reading
    reference_extraction) can resolve their data correctly.
    """
    manifest = get_workflow_manifest(workflow_type, raise_exception=False)
    if manifest is None:
        logger.debug(f"No manifest for {workflow_type}, skipping issue persistence")
        return

    # Load all existing workflow states for the project and revision so manifests
    # that read data from other workflow states can resolve correctly.

    workflow_runs = await get_project_workflow_runs(
        project_id, revision=revision, include_internal=True
    )
    existing_states: list[WorkflowState] = [
        run.state for run in workflow_runs if run.state is not None
    ]

    # Convert state to issues using the manifest
    issues = manifest.convert_state_to_issues(state, existing_states)

    await persist_workflow_issues(
        workflow_run_id=uuid.UUID(workflow_run_id),
        project_id=uuid.UUID(project_id),
        workflow_type=workflow_type,
        issues=issues,
        checkpoint_id=checkpoint_id,
        revision=revision,
    )
