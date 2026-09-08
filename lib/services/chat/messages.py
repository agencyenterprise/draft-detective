"""A conversation as the /chat page sends one for naming.

The page flattens each message to its text before sending, so a transcript is a
list of role/content pairs. This is what the title generator works from; the
turns themselves are checkpointed server-side and never replayed by the client.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatTurnMessage(BaseModel):
    """One message of the conversation, as the client sends it."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(default="")
