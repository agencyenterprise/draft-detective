from abc import ABC, abstractmethod
from typing import List, Type, TypeVar

from langgraph.graph import StateGraph

from lib.config.env import config as env_config
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    DocumentIssue,
    WorkflowGate,
    WorkflowRunType,
)
from lib.workflows.workflow_types import WorkflowState

WorkflowStateType = TypeVar("WorkflowStateType", bound=BaseWorkflowState)
WorkflowConfigType = TypeVar("WorkflowConfigType", bound=BaseWorkflowConfig)


class WorkflowManifest[WorkflowStateType, WorkflowConfigType](ABC):
    """Base class for workflow manifests."""

    # Type of the workflow
    type: WorkflowRunType

    # Name of the workflow
    name: str

    # Description of the workflow
    description: str

    # Whether the workflow needs web search
    needs_web_search: bool = False

    # Internal workflows run as dependencies, not shown in UI
    is_internal: bool = False

    # Experimental workflows are hidden by default in the UI
    is_experimental: bool = False

    # Consents the user must give, per project revision, before this workflow
    # may run. A run started while any of these is unsatisfied is created in
    # AWAITING_APPROVAL and not scheduled; approving the gate releases it.
    # Workflows that required-depend on a gated workflow inherit its gates.
    gates: List[WorkflowGate] = []

    # Whether creating a new revision may re-run this workflow automatically,
    # as part of "re-run previous assessments". Set False for workflows whose
    # inputs are not simply "the current draft" — re-running them the moment a
    # revision appears would either waste a run or produce a guard message.
    auto_rerun_on_new_revision: bool = True

    # If True, workflow always runs even if already completed (when included as dependency)
    # The workflows needs to be idempotent, meaning it can be run multiple times without changing the result and typical execute only "new" content that was not processed in a previous run, reusing cached results from previous runs, like summarization, document conversion, etc (should process only new files in subsequent runs).
    always_run: bool = False

    # Maximum wall-clock duration (seconds) for a single execution of this workflow.
    # Exceeding this transitions the run to FAILED with failure_reason=timeout.
    # Override in subclasses for workflows that legitimately run longer.
    max_duration_seconds: float = 1 * 60 * 60  # 1 hour

    # Maximum number of LangGraph nodes this workflow runs in parallel.
    # Defaults to the global env_config.LANGGRAPH_MAX_CONCURRENCY. Override in
    # workflows that fan out heavy per-item LLM calls (e.g. one web-search
    # agent per reference) to stay under provider rate limits.
    max_concurrency: int = env_config.LANGGRAPH_MAX_CONCURRENCY

    # List of workflow types that this workflow depends on.
    # Used to determine the order in which the workflows should be run.
    # In case a workflow is started and a required dependency is not completed, running or scheduled to run, the workflow will fail to start with an error.
    required_dependencies: List[WorkflowRunType] = []

    # List of workflow types that this workflow depends on optionally.
    # Used to determine the order in which the workflows should be run.
    # In case a workflow is started and an optional dependency is running or scheduled to run, the workflow will wait until it completes to start; otherwise, it will start immediately.
    optional_dependencies: List[WorkflowRunType] = []

    @abstractmethod
    def get_state_type(self) -> Type[WorkflowStateType]:
        """Get the type of the workflow state."""

        raise NotImplementedError()

    @abstractmethod
    def get_config_type(self) -> Type[WorkflowConfigType]:
        """Get the type of the workflow config."""

        raise NotImplementedError()

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""

        raise NotImplementedError()

    @abstractmethod
    async def create_initial_state(
        self,
        config: WorkflowConfigType,
        existing_states: List[WorkflowState],
        revision: int,
        prior_self_state: WorkflowStateType | None = None,
    ) -> WorkflowStateType:
        """Create and return the initial state of the workflow.

        ``prior_self_state`` is the same-type prior run's state (or None). Most
        workflows build fresh from dependency states and ignore it; accumulating
        workflows (e.g. reference_downloader) seed their carried-forward fields
        from it, since each run now gets a fresh langgraph_thread_id and the
        checkpointer no longer carries prior state forward.
        """

        raise NotImplementedError()

    @abstractmethod
    def convert_state_to_issues(
        self, state: WorkflowStateType, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Get issues for a workflow state result."""

        raise NotImplementedError()

    async def on_cancel(self, state: WorkflowStateType) -> WorkflowStateType:
        """
        Called when a workflow run is cancelled or times out. Override to clean up
        per-item statuses (e.g. mark PENDING items CANCELLED) and RETURN the
        updated state; the runner and reaper persist the returned state via
        persist_workflow_run_state.

        The default is a no-op that returns the state unchanged. Override in
        manifests that have per-item statuses that would otherwise remain stuck in
        a 'pending' state after cancellation.
        """
        return state
