"""Tests for Reviewer 2's two-file markdown delivery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.agents.reviewer_2 import (
    _DELIVERY_GUIDANCE,
    PEER_REVIEW_PATH,
    REBUTTAL_PATH,
    Reviewer2Agent,
)
from lib.workflows.simple_deep_agent.agent_types import ReportNotWrittenError


def _agent() -> Reviewer2Agent:
    agent = Reviewer2Agent(MagicMock())
    agent._llm = MagicMock()
    return agent


@pytest.mark.asyncio
async def test_reviewer_2_reads_both_documents_from_files():
    agent = _agent()
    with patch("lib.agents.reviewer_2.create_deep_agent") as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={
                "messages": ["the conversation"],
                "files": {
                    PEER_REVIEW_PATH: {"content": ["# Peer review", "Review body"]},
                    REBUTTAL_PATH: {"content": ["# Rebuttal", "Rebuttal body"]},
                },
            }
        )
        result, messages = await agent.ainvoke({"document_markdown": "# Draft"})

    assert "response_format" not in create_agent.call_args.kwargs
    assert result.peer_review_markdown == "# Peer review\nReview body"
    assert result.rebuttal_markdown == "# Rebuttal\nRebuttal body"
    # The conversation comes back so the workflow can persist it.
    assert messages == ["the conversation"]


@pytest.mark.asyncio
async def test_reviewer_2_fails_when_either_document_is_missing():
    agent = _agent()
    with patch("lib.agents.reviewer_2.create_deep_agent") as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={
                "messages": [],
                "files": {
                    PEER_REVIEW_PATH: {"content": ["# Peer review", "Review body"]}
                },
            }
        )
        with pytest.raises(ReportNotWrittenError, match=REBUTTAL_PATH):
            await agent.ainvoke({"document_markdown": "# Draft"})


@pytest.mark.asyncio
async def test_reviewer_2_can_look_at_the_figures_it_critiques():
    """The tool, its instructions and the runtime context it resolves images
    through all have to arrive together; any one missing surfaces only as a
    tool error deep inside a live run."""
    agent = _agent()
    with patch("lib.agents.reviewer_2.create_deep_agent") as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(
            return_value={
                "messages": [],
                "files": {
                    PEER_REVIEW_PATH: {"content": ["# Peer review"]},
                    REBUTTAL_PATH: {"content": ["# Rebuttal"]},
                },
            }
        )
        await agent.ainvoke({"document_markdown": "# Draft"})

    tool_names = {
        tool.name
        for tool in create_agent.call_args.kwargs["tools"]
        if hasattr(tool, "name")
    }
    assert "view_image" in tool_names
    invoke = create_agent.return_value.ainvoke.call_args
    assert invoke.kwargs["context"] is agent.context
    system_message = invoke.args[0]["messages"][0]
    assert "view_image" in system_message.content
    assert "draftdetective://" in system_message.content


def test_delivery_prompt_names_both_required_files_and_ignores_final_message():
    assert PEER_REVIEW_PATH in _DELIVERY_GUIDANCE
    assert REBUTTAL_PATH in _DELIVERY_GUIDANCE
    assert "write_file" in _DELIVERY_GUIDANCE
    assert "nothing in your final message" in _DELIVERY_GUIDANCE
