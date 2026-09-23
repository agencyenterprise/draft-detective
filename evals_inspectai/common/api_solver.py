"""Inspect agents that upload documents and evaluate the real API workflow."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.log import transcript
from inspect_ai.log._samples import sample_active
from inspect_ai.model import ChatMessage, ModelOutput
from langchain_core.messages.utils import convert_to_messages

from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    poll_until_complete,
)
from evals_inspectai.common.backend import resolve_base_url
from evals_inspectai.common.converters import messages_from_langchain
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.loaders import inline_local_images
from evals_inspectai.common.local_backend import LocalBackend


async def _run_workflow(
    content: str | bytes,
    filename: str,
    workflow_type: str,
    base_url: str,
    timeout_s: float,
    poll_interval_s: float,
) -> tuple[str, list[ChatMessage]]:
    project_id = await create_project_and_start_workflows(
        file_content=content,
        file_name=filename,
        workflow_types=[workflow_type],
        base_url=base_url,
    )
    last_status = ""

    def on_poll(status: str, elapsed: float) -> None:
        nonlocal last_status
        if status != last_status:
            last_status = status
            transcript().info({"status": status, "elapsed_s": round(elapsed, 1)})

    try:
        detail = await poll_until_complete(
            project_id=project_id,
            workflow_type=workflow_type,
            timeout_s=timeout_s,
            interval_s=poll_interval_s,
            on_poll=on_poll,
            base_url=base_url,
        )
    except TimeoutError as exc:
        raise WorkflowCompletionError(str(exc)) from exc

    output = dict(detail.get("state") or {})
    raw_messages = output.pop("messages", [])
    messages = messages_from_langchain(convert_to_messages(raw_messages))
    return json.dumps(output), messages


def _set_output(state: AgentState, result: tuple[str, list[ChatMessage]]) -> AgentState:
    completion, messages = result
    state.output = ModelOutput(completion=completion, model="api")
    if messages:
        # Sibling samples may mutate their own message lists.
        state.messages = deepcopy(messages)
    return state


@agent
def api_workflow_agent(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """Upload sample text as Markdown, embedding any locally referenced images."""

    async def execute(state: AgentState) -> AgentState:
        base_url = await resolve_base_url(local_backend, api_base_url)
        content = inline_local_images(state.messages[0].text) if state.messages else ""
        result = await _run_workflow(
            content,
            "eval-document.md",
            workflow_type,
            base_url,
            timeout_s,
            poll_interval_s,
        )
        return _set_output(state, result)

    return execute


@agent
def api_workflow_agent_file(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """Upload the file at the sample's input path, preserving its bytes/name."""

    async def execute(state: AgentState) -> AgentState:
        base_url = await resolve_base_url(local_backend, api_base_url)
        path = Path(state.messages[0].text)
        result = await _run_workflow(
            path.read_bytes(),
            path.name,
            workflow_type,
            base_url,
            timeout_s,
            poll_interval_s,
        )
        return _set_output(state, result)

    return execute


@agent
def api_workflow_agent_file_cached(
    workflow_type: str,
    output_cache: dict[str, Any],
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """One successful extraction per document/epoch, shared by abbreviation rows.

    The task owns output_cache. Evaluation ID and endpoint also isolate reuse:
    evaluating the same Task object again must invoke fresh workflows. Failed
    extractions are never stored. Each sample receives its own message copy.
    """
    locks: dict[str, asyncio.Lock] = {}

    async def execute(state: AgentState) -> AgentState:
        base_url = await resolve_base_url(local_backend, api_base_url)
        path = Path(state.messages[0].text).resolve()
        active = sample_active()
        if active is None:
            raise RuntimeError("Workflow cache requires an active Inspect sample")
        key = f"{active.eval_id}::{base_url}::{workflow_type}::{_workflow_cache_key(path, active.epoch)}"
        async with locks.setdefault(key, asyncio.Lock()):
            if key not in output_cache:
                output_cache[key] = await _run_workflow(
                    path.read_bytes(),
                    path.name,
                    workflow_type,
                    base_url,
                    timeout_s,
                    poll_interval_s,
                )
        return _set_output(state, output_cache[key])

    return execute


def _workflow_cache_key(file_path: Path, epoch: int) -> str:
    return f"{file_path}::epoch={epoch}"


# Backward-compatible name used by external eval repositories.
api_file_workflow_agent = api_workflow_agent_file
