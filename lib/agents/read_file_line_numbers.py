"""Line numbers on `read_file` results, for agents that report where things are.

deepagents 0.7.14 stopped numbering `read_file` rows: a page now comes back as a
`@@ lines A-B of T @@` status header over verbatim rows. Our agents anchor every
issue, occurrence and citation to line numbers in the file they read, and left to
count rows from the header they land a few lines off (blank lines are the usual
casualty). This middleware numbers the rows again, with deepagents' own gutter
format, and tells the model in the tool descriptions that the numbers are not
part of the file.

A deep agent's default general-purpose subagent does not inherit it: deepagents
gives that subagent only its own default middleware. `build_deep_agent` in
`deep_agent_setup` passes a subagent that runs it too.
"""

import re
from typing import Any, Awaitable, Callable

from deepagents.backends.utils import format_content_with_line_numbers
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

READ_FILE = "read_file"
EDIT_FILE = "edit_file"

# The status header, alone on its row, capturing the range the rows below cover.
_HEADER = re.compile(r"^@@ lines (\d+)-(\d+)(?: of \d+)?(?: \| .*)? @@$")

# A truncation notice can sit above the header; it never runs past a few rows.
_MAX_ROWS_BEFORE_HEADER = 3

_READ_FILE_NOTE = (
    "\n\nEach row below the status header starts with its 1-indexed line number in "
    "the file, then two spaces. The number is not part of the file: cite it as the "
    "line number, and leave it out of any text you copy."
)
_EDIT_FILE_NOTE = (
    "\n\n`read_file` prefixes each row with its line number and two spaces. That "
    "prefix is not part of the file: never include it in `old_string` or "
    "`new_string`."
)


def number_read_file_rows(content: str) -> str:
    """The `read_file` result with each row below its status header numbered.

    Left unchanged when there is no header, or when the rows below it are not the
    one-per-line window the header states (anything else would misnumber them).
    """
    rows = content.split("\n")
    for index, row in enumerate(rows[: _MAX_ROWS_BEFORE_HEADER + 1]):
        header = _HEADER.match(row)
        if header is None:
            continue
        start, end = int(header.group(1)), int(header.group(2))
        body = rows[index + 1 :]
        if len(body) != end - start + 1:
            return content
        numbered = format_content_with_line_numbers(body, start_line=start)
        return "\n".join([*rows[: index + 1], numbered])
    return content


def _with_note(tool: BaseTool, note: str) -> BaseTool:
    if tool.description.endswith(note):
        return tool
    return tool.model_copy(update={"description": tool.description + note})


class ReadFileLineNumbersMiddleware(AgentMiddleware[Any, Any, Any]):
    """Number `read_file` rows and say so in the file tools' descriptions."""

    def _describe(self, request: ModelRequest) -> ModelRequest:
        notes = {READ_FILE: _READ_FILE_NOTE, EDIT_FILE: _EDIT_FILE_NOTE}
        tools = [
            _with_note(tool, notes[tool.name])
            if isinstance(tool, BaseTool) and tool.name in notes
            else tool
            for tool in request.tools
        ]
        return request.override(tools=tools)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._describe(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._describe(request))

    @staticmethod
    def _number(
        request: ToolCallRequest, result: ToolMessage | Command[Any]
    ) -> ToolMessage | Command[Any]:
        if request.tool_call.get("name") != READ_FILE or not isinstance(result, ToolMessage):
            return result
        if not isinstance(result.content, str):
            return result
        numbered = number_read_file_rows(result.content)
        if numbered == result.content:
            return result
        return result.model_copy(update={"content": numbered})

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        return self._number(request, handler(request))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        return self._number(request, await handler(request))

