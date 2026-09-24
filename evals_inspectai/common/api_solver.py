"""Inspect AI agent that runs a workflow end-to-end via the API."""

import asyncio
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, List, Optional, Union

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.log import transcript
from inspect_ai.log._samples import sample_active
from inspect_ai.model import ModelOutput
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    poll_until_complete,
)
from evals_inspectai.common.transcript_replay import (
    Conversation,
    messages_from_state,
    replay_conversations,
)
from evals_inspectai.common.backend import resolve_base_url
from evals_inspectai.common.loaders import inline_local_images
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.local_backend import LocalBackend

logger = logging.getLogger(__name__)


async def _run_workflow(
    content: str | bytes,
    filename: str,
    workflow_type: str,
    base_url: str,
    timeout_s: float,
    poll_interval_s: float,
) -> dict:
    """Run one workflow, retaining the complete state for transcript replay."""
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
    return dict(detail.get("state") or {})


async def _set_workflow_output(
    state: AgentState,
    workflow_state: dict,
    workflow_type: str,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
) -> AgentState:
    # `surface_conversations` removes messages from state, so cached workflow
    # results must be copied before being surfaced for an individual sample.
    output = deepcopy(workflow_state)
    await surface_conversations(state, output, workflow_type, item_messages_key, item_label)
    state.output = ModelOutput(completion=json.dumps(output), model="api")
    return state


@agent
def api_workflow_agent(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """Run a full workflow via the API and capture its state as output.

    Args:
        workflow_type: The WorkflowRunType value to trigger and wait for
            (e.g. "abbreviation_scan_v2").
        timeout_s: Max seconds to wait for workflow completion.
        poll_interval_s: Seconds between polling attempts.
        item_messages_key: For a workflow that fans out, the state list whose
            items each carry their own agent `messages` (e.g. "chunks"). With
            more than one conversation, each is replayed into the transcript
            under its own agent span and the Messages tab is left as is; a
            single conversation goes straight into the transcript and fills
            the Messages tab.
        item_label: How to name one item in the transcript (e.g. "chunk");
            defaults to `item_messages_key`.
    """

    async def execute(state: AgentState) -> AgentState:
        # Figures referenced by local path are embedded as data URIs here, so
        # the backend extracts them like any document's images; the sample's
        # own input stays the readable, path-referencing markdown.
        document_content = (
            inline_local_images(state.messages[0].text) if state.messages else ""
        )

        base_url = await resolve_base_url(local_backend, api_base_url)
        workflow_state = await _run_workflow(
            document_content, "eval-document.md", workflow_type, base_url, timeout_s, poll_interval_s
        )
        return await _set_workflow_output(
            state, workflow_state, workflow_type, item_messages_key, item_label
        )

    return execute


@agent
def api_workflow_agent_file(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """Upload the file at the sample input path, preserving its bytes and name."""

    async def execute(state: AgentState) -> AgentState:
        path = Path(state.messages[0].text)
        base_url = await resolve_base_url(local_backend, api_base_url)
        workflow_state = await _run_workflow(
            path.read_bytes(), path.name, workflow_type, base_url, timeout_s, poll_interval_s
        )
        return await _set_workflow_output(
            state, workflow_state, workflow_type, item_messages_key, item_label
        )

    return execute


@agent
def api_workflow_agent_file_cached(
    workflow_type: str,
    output_cache: dict[str, Any],
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
    local_backend: "LocalBackend | None" = None,
    api_base_url: str | None = None,
) -> Agent:
    """Run a file once per eval/document/epoch and share successful results."""
    locks: dict[str, asyncio.Lock] = {}

    async def execute(state: AgentState) -> AgentState:
        path = Path(state.messages[0].text).resolve()
        active = sample_active()
        if active is None:
            raise RuntimeError("Workflow cache requires an active Inspect sample")
        base_url = await resolve_base_url(local_backend, api_base_url)
        key = f"{active.eval_id}::{base_url}::{workflow_type}::{path}::epoch={active.epoch}"
        async with locks.setdefault(key, asyncio.Lock()):
            if key not in output_cache:
                output_cache[key] = await _run_workflow(
                    path.read_bytes(), path.name, workflow_type, base_url, timeout_s, poll_interval_s
                )
        return await _set_workflow_output(
            state, output_cache[key], workflow_type, item_messages_key, item_label
        )

    return execute


# Backward-compatible name used by external eval repositories.
api_file_workflow_agent = api_workflow_agent_file


async def surface_conversations(
    state: Union[AgentState, TaskState],
    workflow_state: dict,
    workflow_type: str,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
) -> None:
    """Move the workflow's agent conversations from its state into the Inspect log.

    Every conversation is replayed into the transcript. A single conversation
    also fills the Messages tab; a fan-out run's conversations are only in the
    transcript, one agent span each, and the Messages tab is left as is.
    """
    conversations = pop_conversations(
        workflow_state, workflow_type, item_messages_key, item_label
    )
    messages = await replay_conversations(conversations)
    if messages:
        state.messages = messages


def pop_conversations(
    workflow_state: dict,
    workflow_type: str,
    item_messages_key: Optional[str],
    item_label: Optional[str] = None,
) -> List[Conversation]:
    """Remove every agent conversation from the state, in run order.

    Messages are removed so the scored completion stays a compact JSON payload;
    they are surfaced in the Inspect transcript instead. The workflow's own
    top-level conversation comes first, then one per fan-out item that has one.
    """
    conversations: List[Conversation] = []
    top_level = messages_from_state(workflow_state.pop("messages", None) or [])
    if top_level:
        conversations.append(Conversation(label=workflow_type, messages=top_level))
    if not item_messages_key:
        return conversations

    for index, item in enumerate(workflow_state.get(item_messages_key) or []):
        if not isinstance(item, dict):
            continue
        item_messages = messages_from_state(item.pop("messages", None) or [])
        if not item_messages:
            continue
        summary = _item_summary(index, item)
        conversations.append(
            Conversation(
                label=item.get("name") or _item_label(item_label or item_messages_key, summary),
                metadata={item_messages_key: summary},
                messages=item_messages,
            )
        )
    return conversations


def _item_label(key: str, summary: dict) -> str:
    parts = [f"{key} {summary['index']}"]
    if "lines" in summary:
        parts.append(f"lines {summary['lines']}")
    if summary.get("status") not in (None, "completed"):
        parts.append(summary["status"])
    return " · ".join(parts)


def _item_summary(index: int, item: dict) -> dict:
    summary: dict = {"index": index}
    if "start_line" in item and "end_line" in item:
        summary["lines"] = f"{item['start_line']}-{item['end_line']}"
    for field in ("status", "skip_reason", "error"):
        if item.get(field):
            summary[field] = str(item[field])
    return summary
