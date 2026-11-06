"""The passage an issue is about, as every issue payload publishes it.

A passage is the exact words of the main document an issue concerns, quoted on
one line and located when the issue was reported. An issue has at most one,
stored in the ``passage_*`` columns of `Issue`; an issue without one concerns
its whole line range.

It has the shape of a proposed edit's quote (`IssueEditRead` without the
replacement), so the app's highlight and the Word export find both with the
same code.
"""

from pydantic import BaseModel


class IssuePassageRead(BaseModel):
    """Read-only view of an issue's passage."""

    original_text: str
    display_text: str
    display_occurrence: int
    start_line: int
    end_line: int
