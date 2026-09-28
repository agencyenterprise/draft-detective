"""The model an e2e eval runs the workflow on, taken from Inspect's ``--model``.

An e2e eval never calls Inspect's model itself: the workflow runs in the API
server. So ``inspect eval ... --model openai/gpt-5.6-sol`` is forwarded to the
server as the run's model override, and the finished run is checked to have
actually used it. Without ``--model`` Inspect's active model is ``none/none``;
nothing is forwarded and every agent keeps its own model.

The server has to allow the override (``ALLOW_WORKFLOW_MODEL_OVERRIDE=true``).
"""

import re
from typing import Any, Optional

from inspect_ai.model import get_model

from evals_inspectai.common.errors import WorkflowCompletionError

NO_MODEL = "none"

# Inspect provider names that LangChain's init_chat_model spells differently.
LANGCHAIN_PROVIDERS = {"google": "google_genai"}

# What a provider may append to the model it was asked for: OpenAI's date
# ("-2026-08-01"), which the Azure gateway follows with a deployment tag
# ("-2026-07-09-global-aaif"), or Anthropic's ("-20250929"). Anchored on the date,
# as the backend's pricing is, so a different variant ("-mini") still fails.
DATED_SUFFIX = r"-(\d{4}-\d{2}-\d{2}(-[A-Za-z0-9-]+)?|\d{8})"


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


# Where note_served_models keeps the models on a run detail.
SERVED_MODELS_KEY = "served_models"


def note_served_models(run_detail: dict[str, Any]) -> None:
    """Record the models that served the run on its detail, while the replies are there.

    Solvers move the replies out of the state into the transcript before they name
    the sample's output model, so it has to be read before that. The poll helpers
    call this as soon as a run completes.
    """
    run_detail[SERVED_MODELS_KEY] = served_models(run_detail)


def served_models(run_detail: dict[str, Any]) -> list[str]:
    """The models the run's LLM replies reported.

    Read from the replies in the run's state, because the cost breakdown drops any
    model it has no price for, which is exactly where an override can land. Merged
    with what note_served_models recorded, for callers that already moved the
    replies out of the state, and with the breakdown.
    """
    cost = run_detail.get("cost") or {}
    found = set((cost.get("by_model") or {}).keys())
    found.update(run_detail.get(SERVED_MODELS_KEY) or [])
    _collect_reply_models(run_detail.get("state"), found)
    return sorted(found)


def _collect_reply_models(node: Any, found: set[str]) -> None:
    """Add the model named by every serialized AI reply under `node` (a reply carries usage)."""
    if isinstance(node, list):
        for item in node:
            _collect_reply_models(item, found)
        return
    if not isinstance(node, dict):
        return
    if "usage_metadata" in node:
        metadata = node.get("response_metadata")
        if isinstance(metadata, dict):
            name = metadata.get("model_name") or metadata.get("model")
            if name:
                found.add(str(name))
    for value in node.values():
        _collect_reply_models(value, found)


def is_model(served: str, name: str) -> bool:
    """Whether a provider's reported model is `name` itself, or `name` with its date."""
    return re.fullmatch(re.escape(name) + f"({DATED_SUFFIX})?", served) is not None


def output_model_name(run_detail: dict[str, Any]) -> str:
    """What to record as the sample's output model: what the run was served by."""
    return ", ".join(served_models(run_detail)) or requested_model() or "api"


def check_model_used(run_detail: dict[str, Any]) -> None:
    """Raise if a run asked to use ``--model`` recorded or was served another one.

    The recorded model catches a run started without the override (a start path
    that dropped it); the served models catch an agent that ignored it. Providers
    report the bare model name, sometimes with a date suffix, so that is what they
    are compared on.
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
    others = [m for m in served_models(run_detail) if not is_model(m, name)]
    if others:
        raise WorkflowCompletionError(
            f"Run {run.get('id')} asked for {requested!r} but was served by {others}."
        )
