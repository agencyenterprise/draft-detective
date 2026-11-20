"""What the Literature Review and Live Reports workflows hand their deep agent.

Both are simple deep agents with web search that also receive the document's
extracted bibliography and publication date in the user prompt. The node is
captured from the manifest's graph and run undecorated: `register_node` records
progress in the database, which is not what is under test here.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from lib.config.llm_models import web_search_tool
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.skills import load_skill_prompt
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.state import ExtractedReference
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.agent_types import (
    MARKDOWN_REPORT_PATH,
    DeepAgentRun,
)
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

_CASES = [
    (
        WorkflowRunType.LITERATURE_REVIEW_V2,
        "literature-review",
        "### Extracted bibliography",
    ),
]


def _build_nodes(
    workflow_type: WorkflowRunType,
) -> dict[str, Callable[..., Awaitable[dict]]]:
    """The workflow's nodes by progress label, as built before `register_node`."""
    nodes: dict[str, Callable[..., Awaitable[dict]]] = {}

    def capture(name: str):
        def decorate(fn):
            nodes[name] = fn
            return fn

        return decorate

    with patch("lib.workflows.simple_deep_agent.manifest_base.register_node", capture):
        get_workflow_manifest(workflow_type).build_graph()
    return nodes


async def _run_node(
    workflow_type: WorkflowRunType,
    references: list[ExtractedReference],
    publication_date: str | None,
) -> tuple[SimpleDeepAgent, dict]:
    """Run the workflow's only node and return the agent it invoked and its output."""
    manifest = get_workflow_manifest(workflow_type)
    (node,) = _build_nodes(workflow_type).values()

    runtime = MagicMock()
    runtime.context.file_artifacts_service = MockFileArtifactsService(
        extracted_references=references
    )
    runtime.context.agent_model.side_effect = lambda model: model
    invoked: list[SimpleDeepAgent] = []

    async def fake_ainvoke(self: SimpleDeepAgent, prompt_kwargs: dict) -> DeepAgentRun:
        invoked.append(self)
        return DeepAgentRun(files={MARKDOWN_REPORT_PATH: "# Report"})

    config = manifest.get_config_type()(
        project_id=str(uuid.uuid4()),
        type=workflow_type,
        publication_date=publication_date,
    )
    with patch.object(SimpleDeepAgent, "ainvoke", fake_ainvoke):
        output = await node(
            SimpleDeepAgentState(type=workflow_type, config=config), runtime
        )
    (agent,) = invoked
    return agent, output


@pytest.mark.asyncio
@pytest.mark.parametrize(("workflow_type", "skill", "heading"), _CASES)
async def test_user_prompt_is_the_skill_plus_bibliography_and_date(
    workflow_type: WorkflowRunType, skill: str, heading: str
):
    references = [
        ExtractedReference(id="r1", text="Smith (2020). A study."),
        ExtractedReference(id="r2", text="Jones (2021). Another."),
    ]
    agent, _ = await _run_node(workflow_type, references, "2023-05-01")

    assert agent._user_prompt == (
        load_skill_prompt(skill)
        + "\n---\n\n## Inputs for this run\n\n### Document publication date\n2023-05-01\n\n"
        + f"{heading}\n```\n1. Smith (2020). A study.\n2. Jones (2021). Another.\n```\n"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("workflow_type", "skill", "heading"), _CASES)
async def test_missing_inputs_fall_back_to_today_and_a_placeholder(
    workflow_type: WorkflowRunType, skill: str, heading: str
):
    agent, _ = await _run_node(workflow_type, [], None)

    assert (
        f"### Document publication date\n{date.today().isoformat()}\n"
        in agent._user_prompt
    )
    assert f"{heading}\n```\nNo bibliography available.\n```\n" in agent._user_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(("workflow_type", "skill", "heading"), _CASES)
async def test_agent_runs_with_web_search_a_long_timeout_and_its_own_system_prompt(
    workflow_type: WorkflowRunType, skill: str, heading: str
):
    agent, output = await _run_node(workflow_type, [], None)

    assert agent.timeout == 600
    assert agent._tools == [web_search_tool(SimpleDeepAgent.model)]
    assert agent._report_issues is True
    assert agent._propose_edits is False
    assert agent._view_images is False
    assert agent.reasoning == SimpleDeepAgent.reasoning
    assert agent._system_prompt.startswith("You are an expert ")
    assert "`/report.md`" in agent._system_prompt
    assert output["result"].report_markdown == "# Report"
    assert output["messages"] == []


@pytest.mark.parametrize(
    ("workflow_type", "label"),
    [
        (WorkflowRunType.LITERATURE_REVIEW_V2, "Review literature"),
    ],
)
def test_node_keeps_its_progress_label(workflow_type: WorkflowRunType, label: str):
    assert list(_build_nodes(workflow_type)) == [label]
