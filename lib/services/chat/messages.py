"""The conversation as the /chat page sends it, turned into LangChain messages.

The page flattens each message to its text (including the text of any attached
documents) before sending, so a turn is a list of role/content pairs. Tool calls
and reasoning from earlier turns are display-only on the client and are not
replayed to the model, which is the behaviour the page has always had.
"""

from typing import Literal, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field


class ChatTurnMessage(BaseModel):
    """One message of the conversation, as the client sends it."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(default="")


def to_langchain_messages(messages: Sequence[ChatTurnMessage]) -> list[BaseMessage]:
    """Map the client's messages to LangChain's, dropping what the server owns.

    System messages are ignored: the persona is fixed on the server and not
    overridable by the client. Empty messages are dropped too, since an
    assistant turn that only called tools has no text to replay.

    Raises ``ValueError`` when the result does not end with a user message,
    which is the one shape the agent cannot answer.
    """

    converted: list[BaseMessage] = []
    for message in messages:
        text = message.content.strip()
        if not text or message.role == "system":
            continue
        if message.role == "user":
            converted.append(HumanMessage(content=text))
        else:
            converted.append(AIMessage(content=text))

    if not converted or not isinstance(converted[-1], HumanMessage):
        raise ValueError("The conversation must end with a message from the user.")
    return converted
