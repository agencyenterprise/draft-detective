"""Tests for the tools a simple deep-agent manifest hands its agent.

`needs_web_search` gates the user's consent, and the web search tool is the only
way a simple deep agent can reach the web, so the base manifest attaches the tool
exactly when the flag is set.
"""

from unittest.mock import MagicMock

import pytest

from lib.config.llm_models import claude_3_5_sonnet_model, web_search_tool
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest


def test_web_search_workflow_gets_the_web_search_tool():
    manifest = get_workflow_manifest(WorkflowRunType.METHODOLOGICAL_ALIGNMENT)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    assert manifest.needs_web_search is True
    assert manifest.agent_tools(SimpleDeepAgent.model) == [
        web_search_tool(SimpleDeepAgent.model)
    ]


def test_web_search_tool_follows_the_model_the_agent_runs_on():
    manifest = get_workflow_manifest(WorkflowRunType.METHODOLOGICAL_ALIGNMENT)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    assert manifest.agent_tools(claude_3_5_sonnet_model) == [
        web_search_tool(claude_3_5_sonnet_model)
    ]


@pytest.mark.parametrize(
    "workflow_type",
    [WorkflowRunType.RESULTS_EXTRACTION, WorkflowRunType.FIGURES_TABLES_CHECK],
)
def test_document_only_workflows_get_no_extra_tools(workflow_type: WorkflowRunType):
    manifest = get_workflow_manifest(workflow_type)
    assert isinstance(manifest, SimpleDeepAgentManifest)
    assert manifest.needs_web_search is False
    assert manifest.agent_tools(SimpleDeepAgent.model) == []


def test_timeout_override_shadows_the_class_default():
    default = SimpleDeepAgent(MagicMock(), user_prompt="x")
    longer = SimpleDeepAgent(MagicMock(), user_prompt="x", timeout=600)
    assert longer.timeout == 600
    assert default.timeout == SimpleDeepAgent.timeout
    assert SimpleDeepAgent.timeout != 600
