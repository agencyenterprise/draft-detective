"""Inspect AI agent that runs a workflow end-to-end via the API."""

import json
import logging
from typing import List, Optional, Union

from inspect_ai.agent import Agent, AgentState, agent
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
from evals_inspectai.common.loaders import inline_local_images
from evals_inspectai.common.errors import WorkflowCompletionError

logger = logging.getLogger(__name__)


@agent
def api_workflow_agent(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
    item_messages_key: Optional[str] = None,
    item_label: Optional[str] = None,
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

        project_id = await create_project_and_start_workflows(
            file_content=document_content,
            file_name="eval-document.md",
            workflow_types=[workflow_type],
        )

        try:
            run_detail = await poll_until_complete(
                project_id=project_id,
                workflow_type=workflow_type,
                timeout_s=timeout_s,
                interval_s=poll_interval_s,
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}

        await surface_conversations(
            state, workflow_state, workflow_type, item_messages_key, item_label
        )

        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return execute


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
