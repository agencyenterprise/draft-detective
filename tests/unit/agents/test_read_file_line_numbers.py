"""Numbered `read_file` rows, which our agents need to report line numbers."""

from typing import Any

import pytest
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from lib.agents.deep_agent_setup import agent_input, build_deep_agent, general_purpose_subagent
from lib.agents.read_file_line_numbers import (
    ReadFileLineNumbersMiddleware,
    number_read_file_rows,
)


def test_rows_are_numbered_from_the_header_range():
    content = "@@ lines 9-11 of 20 | next offset 11 @@\nalpha\n\ngamma"
    assert number_read_file_rows(content) == (
        "@@ lines 9-11 of 20 | next offset 11 @@\n 9  alpha\n10  \n11  gamma"
    )


def test_a_notice_above_the_header_is_kept():
    content = "[Output was truncated]\n@@ lines 1-2 of 2 @@\na\nb"
    assert number_read_file_rows(content) == "[Output was truncated]\n@@ lines 1-2 of 2 @@\n1  a\n2  b"


@pytest.mark.parametrize(
    "content",
    [
        "@@ lines 1-3 of 3 @@\nonly two\nrows",  # rows do not match the range
        "Error: file not found",
        "a file with no header\n@@ lines 1-1 @@ further down\nx\ny\nz\nw",
    ],
)
def test_anything_else_is_left_alone(content: str):
    assert number_read_file_rows(content) == content


class _FakeModel(GenericFakeChatModel):
    seen_tools: dict[str, str] = {}

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_FakeModel":
        self.seen_tools.update({t.name: t.description for t in tools if hasattr(t, "name")})
        return self


@pytest.mark.asyncio
async def test_an_agent_reads_numbered_rows_and_is_told_why():
    read = AIMessage(
        content="",
        tool_calls=[{"name": "read_file", "args": {"file_path": "/main.md", "offset": 1, "limit": 3}, "id": "c1"}],
    )
    model = _FakeModel(messages=iter([read, AIMessage(content="done")]))
    agent = create_deep_agent(model=model, middleware=[ReadFileLineNumbersMiddleware()])

    result = await agent.ainvoke(
        agent_input({"/main.md": create_file_data("Title\n\nFirst.\n\nSecond.")}, [HumanMessage("read")])
    )

    (tool_message,) = [m for m in result["messages"] if m.type == "tool"]
    assert tool_message.content.split("\n")[1:] == ["2  ", "3  First.", "4  "]
    assert "line number" in model.seen_tools["read_file"]
    assert "never include it in `old_string`" in model.seen_tools["edit_file"]


class _RecordingModel(_FakeModel):
    """Keeps every `read_file` result it is shown, parent's and subagent's alike."""

    reads: list[str] = []

    def _generate(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
        self.reads.extend(
            str(m.content) for m in messages if m.type == "tool" and "@@ lines" in str(m.content)
        )
        return super()._generate(messages, *args, **kwargs)


@pytest.mark.asyncio
async def test_build_deep_agent_numbers_delegated_reads_too():
    script = [
        AIMessage(
            content="",
            tool_calls=[{"name": "task", "args": {"description": "Read /main.md.", "subagent_type": "general-purpose"}, "id": "t1"}],
        ),
        AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {"file_path": "/main.md", "offset": 0, "limit": 3}, "id": "r1"}],
        ),
        AIMessage(content="subagent done"),
        AIMessage(content="parent done"),
    ]
    model = _RecordingModel(messages=iter(script))
    agent = build_deep_agent(model=model)

    await agent.ainvoke(agent_input({"/main.md": create_file_data("Title\n\nBody")}, [HumanMessage("go")]))

    assert model.reads == ["@@ lines 1-3 of 3 @@\n1  Title\n2  \n3  Body"]


def test_the_subagent_keeps_the_parents_skills():
    assert general_purpose_subagent(skills=["/skills/"])["skills"] == ["/skills/"]
    assert "skills" not in general_purpose_subagent()
