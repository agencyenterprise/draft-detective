"""Inspect AI agent that runs a workflow end-to-end via the API."""

import json
import logging

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ModelOutput
from langchain_core.messages.utils import convert_to_messages

from evals_inspectai.common.api_client import (
    poll_until_complete,
    upload_and_start_analysis,
)
from evals_inspectai.common.converters import messages_from_langchain

logger = logging.getLogger(__name__)


@agent
def api_workflow_agent(
    workflow_type: str,
    timeout_s: float = 300,
    poll_interval_s: float = 5,
) -> Agent:
    """Run a full workflow via the API and capture its state as output.

    Args:
        workflow_type: The WorkflowRunType value to trigger and wait for
            (e.g. "abbreviation_scan_v2").
        timeout_s: Max seconds to wait for workflow completion.
        poll_interval_s: Seconds between polling attempts.
    """

    async def execute(state: AgentState) -> AgentState:
        document_content = state.messages[0].text if state.messages else ""

        project_id = await upload_and_start_analysis(
            file_content=document_content,
            file_name="eval-document.md",
            workflow_types=[workflow_type],
        )

        run_detail = await poll_until_complete(
            project_id=project_id,
            workflow_type=workflow_type,
            timeout_s=timeout_s,
            interval_s=poll_interval_s,
        )

        workflow_state = run_detail.get("state") or {}

        raw_messages = workflow_state.pop("messages", [])
        if raw_messages:
            lc_messages = convert_to_messages(raw_messages)
            state.messages = messages_from_langchain(lc_messages)

        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return execute
