import builtins
import types
from abc import ABC, abstractmethod
from typing import cast, get_args, get_origin

from langgraph.graph import StateGraph

from lib.config.env import config as env_config
from lib.workflows.models import (
    BaseWorkflowConfig,
    BaseWorkflowState,
    DocumentIssue,
    WorkflowGate,
    WorkflowRunType,
)
from lib.workflows.util import pinned_run_type
from lib.workflows.workflow_types import WorkflowState


class WorkflowManifest[
    WorkflowStateType: BaseWorkflowState,
    WorkflowConfigType: BaseWorkflowConfig,
](ABC):
    """Base class for workflow manifests."""

    # Type of the workflow. A state that pins its type with
    # `type: Literal[WorkflowRunType.X]` sets it (see __init_subclass__); only
    # manifests sharing a state, like the simple deep agents, declare it.
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
    gates: list[WorkflowGate] = []

    # Whether creating a new revision may re-run this workflow automatically,
    # as part of "re-run previous assessments". Set False for workflows whose
    # inputs are not simply "the current draft" — re-running them the moment a
    # revision appears would either waste a run or produce a guard message.
    auto_rerun_on_new_revision: bool = True

    # Whether each run is a request of its own, reading only the inputs its
    # config names. Such runs survive a new revision instead of being cancelled
    # by it, and runs of the type do not queue behind each other, since none
    # reads or writes what another does.
    independent_runs: bool = False

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
    # Starting several workflows at once also schedules these (transitively)
    # unless an existing run can be reused (see _reused_dependency_run in
    # lib/api/services/workflow_batch.py). A run waits for each to complete;
    # it is cancelled if one last ended cancelled or failed, or never ran
    # (see lib/services/workflow_runs/promotion_plan.py).
    required_dependencies: list[WorkflowRunType] = []

    # List of workflow types that this workflow depends on optionally.
    # Used to determine the order in which the workflows should be run.
    # In case a workflow is started and an optional dependency is pending, running or awaiting approval, the workflow waits until it ends, in any status, before starting; otherwise, it starts immediately.
    optional_dependencies: list[WorkflowRunType] = []

    # The state and config classes named in the subclass's
    # WorkflowManifest[State, Config] base, filled in by __init_subclass__.
    _state_type: builtins.type[BaseWorkflowState] | None = None
    _config_type: builtins.type[BaseWorkflowConfig] | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for base in types.get_original_bases(cls):
            if get_origin(base) is not WorkflowManifest:
                continue
            state_type, config_type = get_args(base)
            # A subclass that stays generic passes type parameters, not classes.
            if isinstance(state_type, type) and isinstance(config_type, type):
                cls._state_type = state_type
                cls._config_type = config_type
                cls._take_type_from_state(state_type)

    @classmethod
    def _take_type_from_state(
        cls, state_type: builtins.type[BaseWorkflowState]
    ) -> None:
        """Set ``type`` from the state's ``type: Literal[...]``, if it has one."""

        run_type = pinned_run_type(state_type)
        if run_type is None:
            return
        # Declaring it as well would leave two places to keep in step.
        if "type" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} declares type, which {state_type.__name__} "
                "already sets with its Literal: remove the declaration"
            )
        cls.type = run_type

    def get_state_type(self) -> builtins.type[WorkflowStateType]:
        """Get the type of the workflow state."""

        if self._state_type is None:
            raise TypeError(f"{type(self).__name__} does not name its state type")
        return cast(builtins.type[WorkflowStateType], self._state_type)

    def get_config_type(self) -> builtins.type[WorkflowConfigType]:
        """Get the type of the workflow config."""

        if self._config_type is None:
            raise TypeError(f"{type(self).__name__} does not name its config type")
        return cast(builtins.type[WorkflowConfigType], self._config_type)

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""

        raise NotImplementedError()

    async def create_initial_state(
        self,
        config: WorkflowConfigType,
        existing_states: list[WorkflowState],
        revision: int,
        prior_self_state: WorkflowStateType | None = None,
    ) -> WorkflowStateType:
        """Create and return the initial state of the workflow.

        The default is a fresh state holding only the type and the config, every
        other field at its default. Override in workflows that start from more:
        the main file id, dependency states, or ``prior_self_state``, the
        same-type prior run's state (or None). Accumulating workflows (e.g.
        reference_downloader) seed their carried-forward fields from it, since
        each run gets a fresh langgraph_thread_id and the checkpointer no longer
        carries prior state forward.
        """

        # The base state declares neither field: each workflow's state does.
        return self.get_state_type().model_validate(
            {"type": self.type, "config": config}
        )

    @abstractmethod
    def convert_state_to_issues(
        self, state: WorkflowStateType, other_states: list[WorkflowState]
    ) -> list[DocumentIssue]:
        """Get issues for a workflow state result."""

        raise NotImplementedError()

    async def on_cancel(self, state: WorkflowStateType) -> WorkflowStateType:
        """
        Called when a running workflow is cancelled or exceeds max_duration_seconds,
        and when the reaper fails a stuck run that has a saved state. Override to
        clean up per-item statuses (e.g. mark PENDING items CANCELLED) and RETURN
        the updated state; the runner and reaper persist the returned state via
        persist_workflow_run_state.

        The runner passes the state it has accumulated in memory. The reaper
        passes the run's saved state_json, possibly from another pod. A run
        cancelled by the dependency wait itself (a required dependency ended
        CANCELLED or FAILED), or that fails with an unhandled exception or a
        dependency timeout, gets no call. A run cancelled by other means while it
        waits is only noticed at its first node, and gets the call there. The
        hook is best-effort: an error it raises is logged and the run's outcome
        stands.

        The default is a no-op that returns the state unchanged. Override in
        manifests that have per-item statuses that would otherwise remain stuck in
        a 'pending' state after cancellation.
        """
        return state
