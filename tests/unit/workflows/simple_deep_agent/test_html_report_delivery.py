"""Tests for report-file delivery in the shared deep-agent workflows."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from lib.workflows.literature_review_v2.nodes.literature_review import (
    _SYSTEM_PROMPT as LITERATURE_REVIEW_PROMPT,
)
from lib.workflows.live_reports_v2.nodes.live_reports import (
    _SYSTEM_PROMPT as LIVE_REPORTS_PROMPT,
)
from lib.config.llm_models import gpt_5_6_terra_model, web_search_tool
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.simple_deep_agent.agent import (
    _SYSTEM_PROMPT as SIMPLE_AGENT_PROMPT,
)
from lib.workflows.simple_deep_agent.agent import (
    SimpleDeepAgent,
)
from lib.workflows.simple_deep_agent.agent_types import (
    DEEP_AGENT_RECURSION_LIMIT,
    MARKDOWN_REPORT_PATH,
    REPORT_PATH,
    DeepAgentResult,
    DeepAgentRun,
    IssueItem,
    ReportNotWrittenError,
)
from lib.workflows.simple_deep_agent.manifest_base import (
    HtmlReportDeepAgentManifest,
    SimpleDeepAgentManifest,
)
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState

_HTML_WORKFLOWS = [
    WorkflowRunType.REVISION_PLANNING_SUMMARY,
    WorkflowRunType.REVIEWER_COVERAGE_REPORT,
    WorkflowRunType.REVIEWER_RESPONSE_MEMOS,
]

_MARKDOWN_WORKFLOWS = [
    WorkflowRunType.ADVOCACY_TONE_V2,
    WorkflowRunType.DOCUMENT_STRUCTURE,
    WorkflowRunType.FIGURES_TABLES_CHECK,
    WorkflowRunType.LITERATURE_REVIEW_V2,
    WorkflowRunType.LIVE_REPORTS_V2,
    WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
    WorkflowRunType.RECOMMENDATION_CHECK,
    WorkflowRunType.RESULTS_EXTRACTION,
]

_HTML_REPORT = "<!doctype html><html><body><h1>Report</h1></body></html>"
_MARKDOWN_REPORT = "# Report\n\nReview complete."


def _stub_agent(report_issues: bool) -> SimpleDeepAgent:
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(
        return_value={}
    )
    agent = SimpleDeepAgent(
        context=context,
        user_prompt="rules",
        report_issues=report_issues,
    )
    agent._llm = MagicMock()
    return agent


def _html_manifest() -> HtmlReportDeepAgentManifest:
    manifest = get_workflow_manifest(WorkflowRunType.REVISION_PLANNING_SUMMARY)
    assert isinstance(manifest, HtmlReportDeepAgentManifest)
    return manifest


def _markdown_manifest() -> SimpleDeepAgentManifest:
    manifest = get_workflow_manifest(WorkflowRunType.FIGURES_TABLES_CHECK)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    return manifest


def test_html_report_is_read_from_the_agent_filesystem():
    run = DeepAgentRun(files={"/main.md": "# doc", REPORT_PATH: _HTML_REPORT})
    assert _html_manifest()._to_state_result(run).report_html == _HTML_REPORT


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({}, id="no files at all"),
        pytest.param({"/main.md": "# doc"}, id="wrote nothing"),
        pytest.param({REPORT_PATH: ""}, id="empty report"),
        pytest.param({REPORT_PATH: "   \n  "}, id="whitespace only"),
        pytest.param({"/report.htm": _HTML_REPORT}, id="wrong path"),
    ],
)
def test_a_missing_html_report_fails_the_run(files: dict[str, str]):
    with pytest.raises(ReportNotWrittenError) as caught:
        _html_manifest()._to_state_result(DeepAgentRun(files=files))
    assert REPORT_PATH in str(caught.value)


def test_markdown_report_and_tool_issues_are_mapped_to_state():
    issue = IssueItem(
        title="Missing caption",
        description="Figure 1 has no caption.",
        severity="medium",
        start_line=12,
        end_line=12,
    )
    run = DeepAgentRun(
        files={MARKDOWN_REPORT_PATH: _MARKDOWN_REPORT},
        reported_issues=[issue],
    )

    result = _markdown_manifest()._to_state_result(run)

    assert result.report_markdown == _MARKDOWN_REPORT
    assert result.issues == [issue]
    assert result.report_html == ""


@pytest.mark.parametrize(
    "files",
    [
        {},
        {MARKDOWN_REPORT_PATH: ""},
        {MARKDOWN_REPORT_PATH: " \n "},
        {"/report.markdown": _MARKDOWN_REPORT},
    ],
)
def test_a_missing_markdown_report_fails_the_run(files: dict[str, str]):
    with pytest.raises(ReportNotWrittenError, match=MARKDOWN_REPORT_PATH):
        _markdown_manifest()._to_state_result(DeepAgentRun(files=files))


def test_zero_tool_calls_means_zero_issues():
    result = _markdown_manifest()._to_state_result(
        DeepAgentRun(
            files={MARKDOWN_REPORT_PATH: _MARKDOWN_REPORT},
        )
    )
    assert result.issues == []


def test_the_final_message_cannot_influence_either_report():
    final_message = AIMessage(content='{"report_markdown":"wrong"}{"issues":[]}')
    markdown = _markdown_manifest()._to_state_result(
        DeepAgentRun(
            files={MARKDOWN_REPORT_PATH: _MARKDOWN_REPORT},
            messages=[final_message],
        )
    )
    html = _html_manifest()._to_state_result(
        DeepAgentRun(files={REPORT_PATH: _HTML_REPORT}, messages=[final_message])
    )
    assert markdown.report_markdown == _MARKDOWN_REPORT
    assert html.report_html == _HTML_REPORT


@pytest.mark.parametrize("workflow_type", _HTML_WORKFLOWS)
def test_html_workflows_do_not_collect_issues(workflow_type: WorkflowRunType):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, HtmlReportDeepAgentManifest)
    assert manifest.report_issues is False


@pytest.mark.parametrize("workflow_type", _HTML_WORKFLOWS)
def test_html_prompts_ask_for_a_file_write(workflow_type: WorkflowRunType):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, HtmlReportDeepAgentManifest)
    prompt = manifest.system_prompt or ""
    assert REPORT_PATH in prompt
    assert "write_file" in prompt
    assert "report_html" not in prompt


@pytest.mark.parametrize("workflow_type", _MARKDOWN_WORKFLOWS)
def test_markdown_workflows_collect_issues(workflow_type: WorkflowRunType):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    assert manifest.report_issues is True


@pytest.mark.parametrize(
    "prompt",
    [SIMPLE_AGENT_PROMPT, LITERATURE_REVIEW_PROMPT, LIVE_REPORTS_PROMPT],
)
def test_markdown_prompts_name_both_delivery_channels(prompt: str):
    assert MARKDOWN_REPORT_PATH in prompt
    assert "write_file" in prompt
    assert "report_issue" in prompt
    assert "final message" in prompt


@pytest.mark.parametrize("prompt", [LITERATURE_REVIEW_PROMPT, LIVE_REPORTS_PROMPT])
def test_custom_prompts_do_not_repeat_the_issue_tool_schema(prompt: str):
    for field in (
        "`title`",
        "`description`",
        "`long_description`",
        "`suggested_action`",
        "`start_line`",
        "`end_line`",
    ):
        assert field not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_issues, expected_tool_names",
    [
        pytest.param(False, set(), id="html report"),
        pytest.param(
            True,
            {"report_issue"},
            id="markdown report",
        ),
    ],
)
async def test_agent_omits_response_format_and_adds_tools_when_needed(
    report_issues: bool, expected_tool_names: set[str]
):
    agent = _stub_agent(report_issues)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    assert "response_format" not in create_agent.call_args.kwargs
    tool_names = {
        tool.name
        for tool in create_agent.call_args.kwargs["tools"]
        if hasattr(tool, "name")
    }
    assert tool_names == expected_tool_names


@pytest.mark.asyncio
async def test_issue_tool_is_added_without_replacing_workflow_tools():
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(
        return_value={}
    )
    agent = SimpleDeepAgent(
        context=context,
        user_prompt="rules",
        tools=[web_search_tool(gpt_5_6_terra_model)],
    )
    agent._llm = MagicMock()

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    tools = create_agent.call_args.kwargs["tools"]
    assert {tool.name for tool in tools if hasattr(tool, "name")} == {"report_issue"}
    assert web_search_tool(gpt_5_6_terra_model) in tools


@pytest.mark.asyncio
async def test_agent_returns_files_and_collected_issue_state():
    agent = _stub_agent(True)

    async def invoke_agent(_input: dict, config: dict, **_kwargs) -> dict:
        tools = {
            tool.name: tool
            for tool in create_agent.call_args.kwargs["tools"]
            if hasattr(tool, "name")
        }
        tools["report_issue"].invoke(
            {
                "title": "Missing methods",
                "description": "No methods section was found.",
                "severity": "high",
                "start_line": 1,
                "end_line": 1,
            }
        )
        return {
            "messages": [],
            "files": {
                MARKDOWN_REPORT_PATH: {"content": ["# Report", "", "One issue found."]}
            },
        }

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(side_effect=invoke_agent)
        run = await agent.ainvoke({})

    assert run.files == {MARKDOWN_REPORT_PATH: "# Report\n\nOne issue found."}
    assert [issue.title for issue in run.reported_issues] == ["Missing methods"]


_IMAGE_WORKFLOWS = [
    WorkflowRunType.FIGURES_TABLES_CHECK,
    WorkflowRunType.RESULTS_EXTRACTION,
    WorkflowRunType.INFERENCE_VALIDATION_V2,
    WorkflowRunType.RECOMMENDATION_CHECK,
]

_TEXT_ONLY_WORKFLOWS = [
    WorkflowRunType.ADVOCACY_TONE_V2,
    WorkflowRunType.DOCUMENT_STRUCTURE,
    WorkflowRunType.LITERATURE_REVIEW_V2,
    WorkflowRunType.LIVE_REPORTS_V2,
    WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
    *_HTML_WORKFLOWS,
]


def _image_agent(system_prompt: str | None) -> SimpleDeepAgent:
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(
        return_value={}
    )
    agent = SimpleDeepAgent(
        context=context,
        user_prompt="rules",
        system_prompt=system_prompt,
        view_images=True,
    )
    agent._llm = MagicMock()
    return agent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "system_prompt", [None, "Custom reviewer instructions."], ids=["default", "custom"]
)
async def test_image_tool_instructions_travel_with_the_tool(
    system_prompt: str | None,
):
    """Opting in binds view_image and appends its instructions to whichever
    system prompt is in use, so a workflow that overrides the prompt still
    tells the model what a `draftdetective://` src is."""
    agent = _image_agent(system_prompt)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    tool_names = {
        tool.name
        for tool in create_agent.call_args.kwargs["tools"]
        if hasattr(tool, "name")
    }
    assert "view_image" in tool_names
    system_message = create_agent.return_value.ainvoke.call_args.args[0]["messages"][0]
    assert "view_image" in system_message.content
    assert "draftdetective://" in system_message.content
    if system_prompt is not None:
        assert system_message.content.startswith(system_prompt)


@pytest.mark.asyncio
async def test_image_tool_is_off_by_default():
    """A bound tool is an invitation: text-only checks must not be offered
    images, nor told about a tool they do not have."""
    agent = _stub_agent(True)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    tool_names = {
        tool.name
        for tool in create_agent.call_args.kwargs["tools"]
        if hasattr(tool, "name")
    }
    assert "view_image" not in tool_names
    system_message = create_agent.return_value.ainvoke.call_args.args[0]["messages"][0]
    assert "view_image" not in system_message.content


@pytest.mark.parametrize("workflow_type", _IMAGE_WORKFLOWS)
def test_workflows_whose_judgment_can_hinge_on_a_figure_view_images(
    workflow_type: WorkflowRunType,
):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    assert manifest.view_images is True


@pytest.mark.parametrize("workflow_type", _TEXT_ONLY_WORKFLOWS)
def test_text_only_workflows_do_not_view_images(workflow_type: WorkflowRunType):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, (SimpleDeepAgentManifest, HtmlReportDeepAgentManifest))
    assert manifest.view_images is False


@pytest.mark.asyncio
async def test_manifest_passes_its_image_flag_to_the_agent():
    """The flag is only as good as the node that forwards it. The node is run
    undecorated: `register_node` records progress in the database, which is
    not what is under test here."""
    manifest = get_workflow_manifest(WorkflowRunType.FIGURES_TABLES_CHECK)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    nodes: dict[str, object] = {}

    def capture_node(name: str):
        def decorate(fn):
            nodes[name] = fn
            return fn

        return decorate

    with (
        patch(
            "lib.workflows.simple_deep_agent.manifest_base.register_node", capture_node
        ),
        patch(
            "lib.workflows.simple_deep_agent.manifest_base.SimpleDeepAgent"
        ) as agent_cls,
    ):
        agent_cls.return_value.ainvoke = AsyncMock(
            return_value=DeepAgentRun(files={MARKDOWN_REPORT_PATH: _MARKDOWN_REPORT})
        )
        manifest.build_graph()
        run_agent = nodes[manifest.name]
        assert callable(run_agent)
        await run_agent(
            SimpleDeepAgentState(
                type=manifest.type,
                config=manifest.get_config_type()(
                    project_id=str(uuid.uuid4()), type=manifest.type
                ),
            ),
            MagicMock(),
        )

    assert agent_cls.call_args.kwargs["view_images"] is True


@pytest.mark.asyncio
async def test_runtime_context_is_passed_to_the_deep_agent():
    """Tools taking ToolRuntime[ContextSchema] (view_image) read the workflow
    context through the runtime; forgetting to pass it would surface only as
    tool errors deep inside a live run."""
    agent = _stub_agent(True)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    assert (
        create_agent.return_value.ainvoke.call_args.kwargs["context"] is agent.context
    )


@pytest.mark.asyncio
async def test_the_agent_spends_its_own_recursion_budget():
    """Issue reporting costs super-steps, so the budget is not LangGraph's default.

    One `report_issue` call per model turn means the step budget now scales with
    the number of findings. The explicit limit is both a raise over the 100 that
    predates tool-reported issues and a cap well under LangGraph's 10007 default,
    so a runaway loop still terminates.
    """
    agent = _stub_agent(True)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({})

    config = create_agent.return_value.ainvoke.call_args.kwargs["config"]
    assert config["recursion_limit"] == DEEP_AGENT_RECURSION_LIMIT
    assert DEEP_AGENT_RECURSION_LIMIT > 100


@pytest.mark.asyncio
async def test_an_explicit_config_still_wins():
    """The default is a floor for callers, not something they cannot override."""
    agent = _stub_agent(True)

    with patch(
        "lib.workflows.simple_deep_agent.agent.build_deep_agent"
    ) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={"messages": [], "files": {}}
        )
        await agent.ainvoke({}, config={"recursion_limit": 12})

    config = create_agent.return_value.ainvoke.call_args.kwargs["config"]
    assert config["recursion_limit"] == 12


def test_state_result_shape_is_unchanged():
    assert set(DeepAgentResult.model_fields) == {
        "issues",
        "report_markdown",
        "report_html",
    }
    assert set(SimpleDeepAgentState.model_fields) >= {
        "type",
        "config",
        "result",
        "messages",
    }
