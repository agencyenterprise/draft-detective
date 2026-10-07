"""The system prompt states the document's line count, so a line threshold in a skill
(split a long document among sub-agents) is checked before the review starts."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepagents.backends.utils import create_file_data, slice_read_response
from langchain_core.messages import AIMessage

from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent, _document_size_note
from lib.workflows.simple_deep_agent.agent_types import MAIN_DOCUMENT_PATH


def test_note_counts_lines_like_read_file_and_is_empty_without_a_document():
    assert "`/main.md` has 3 lines" in _document_size_note("# Title\n\nBody.\n")
    assert "`lines A-B of 3`" in _document_size_note("# Title\n\nBody.")
    assert _document_size_note(None) == ""


@pytest.mark.parametrize("text", ["# Title\n\nBody.\n", "# Title\n\nBody.", "one\n\n\ntwo\n\n"])
def test_note_matches_the_total_read_file_reports(text: str):
    total = slice_read_response(create_file_data(text), 0, 1000).total_lines
    assert f"`/main.md` has {total} lines" in _document_size_note(text)


@pytest.mark.asyncio
async def test_system_prompt_carries_the_line_count():
    files: dict[str, Any] = {MAIN_DOCUMENT_PATH: create_file_data("one\ntwo\nthree\nfour")}
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(return_value=files)
    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(return_value={"files": {}, "messages": [AIMessage(content="done")]})

    with (
        patch.object(SimpleDeepAgent, "llm", new=MagicMock()),
        patch("lib.workflows.simple_deep_agent.agent.build_deep_agent", return_value=fake_agent),
    ):
        await SimpleDeepAgent(context, user_prompt="x").ainvoke({})

    system_message = fake_agent.ainvoke.call_args.args[0]["messages"][0]
    assert "`/main.md` has 4 lines" in system_message.content
