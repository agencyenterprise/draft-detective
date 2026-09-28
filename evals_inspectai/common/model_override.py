"""The model an e2e eval runs the workflow on, taken from Inspect's ``--model``.

An e2e eval never calls Inspect's model itself: the workflow runs in the API
server. So ``inspect eval ... --model openai/gpt-5.6-sol`` is forwarded to the
server as the run's model override, and the finished run is checked to have
actually used it. Without ``--model`` Inspect's active model is ``none/none``;
nothing is forwarded and every agent keeps its own model.

The server has to allow the override (``ALLOW_WORKFLOW_MODEL_OVERRIDE=true``).
"""

from typing import Any, Optional

from inspect_ai.model import get_model

from evals_inspectai.common.errors import WorkflowCompletionError

NO_MODEL = "none"

# Inspect provider names that LangChain's init_chat_model spells differently.
LANGCHAIN_PROVIDERS = {"google": "google_genai"}


def requested_model() -> Optional[str]:
    """The LangChain model name to send with a workflow start, or None to keep the agents' own."""
    try:
        active = str(get_model())
    except ValueError:
        # Outside an eval, with no INSPECT_EVAL_MODEL either (a helper script).
        return None
    provider, _, name = active.partition("/")
    if provider == NO_MODEL:
        return None
    return f"{LANGCHAIN_PROVIDERS.get(provider, provider)}:{name}"


def served_models(run_detail: dict[str, Any]) -> list[str]:
    """The models the run's LLM calls reported, from its cost breakdown."""
    cost = run_detail.get("cost") or {}
    return sorted((cost.get("by_model") or {}).keys())


def output_model_name(run_detail: dict[str, Any]) -> str:
    """What to record as the sample's output model: what the run was served by."""
    return ", ".join(served_models(run_detail)) or requested_model() or "api"


def check_model_used(run_detail: dict[str, Any]) -> None:
    """Raise if a run asked to use ``--model`` recorded or was served another one.

    The recorded model catches a run started without the override (a start path
    that dropped it); the served models catch an agent that ignored it. Providers
    report the bare model name, often with a date suffix, so that is what they are
    compared on.
    """
    requested = requested_model()
    if requested is None:
        return
    run = run_detail.get("run") or {}
    recorded = run.get("model")
    if recorded != requested:
        raise WorkflowCompletionError(
            f"Run {run.get('id')} was started with model {recorded!r}, not {requested!r}."
        )
    name = requested.partition(":")[2]
    others = [m for m in served_models(run_detail) if not m.startswith(name)]
    if others:
        raise WorkflowCompletionError(
            f"Run {run.get('id')} asked for {requested!r} but was served by {others}."
        )
