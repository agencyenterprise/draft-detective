"""A short title for a chat thread, from its opening messages."""

import logging
from typing import Any, Optional, Sequence

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from lib.config.env import get_model_api_key
from lib.config.llm_models import gpt_5_6_luna_model
from lib.services.chat.messages import ChatTurnMessage

logger = logging.getLogger(__name__)

# The task is a label, not a judgment, so the cheapest current-generation tier at
# the lowest reasoning effort. Reasoning models reject a temperature, so none is set.
TITLE_MODEL = gpt_5_6_luna_model
TITLE_REASONING = {"effort": "low"}
FALLBACK_TITLE = "New chat"
MAX_TITLE_LENGTH = 80

_INSTRUCTIONS = (
    "You name conversations. Given a transcript, reply with a short, specific "
    "title for it (3 to 6 words) and nothing else: no quotes, no trailing "
    "punctuation, and never a reply to the conversation itself."
)


async def generate_title(
    messages: Sequence[ChatTurnMessage], api_key: Optional[str] = None
) -> str:
    """Never raises: a title is decoration, so a failure yields the fallback."""

    resolved = api_key or get_model_api_key(TITLE_MODEL.name)
    kwargs: dict[str, Any] = {
        "model": TITLE_MODEL.model_name,
        "reasoning": TITLE_REASONING,
        "timeout": 15,
        "max_retries": 1,
    }
    if resolved:
        kwargs["api_key"] = resolved

    # One message carrying the transcript, rather than replaying the turns: a
    # reasoning model handed the turns tends to answer the last one instead.
    transcript = "\n\n".join(
        f"{message.role}: {message.content.strip()}"
        for message in messages
        if message.content.strip()
    )
    try:
        response = await init_chat_model(**kwargs).ainvoke(
            [
                SystemMessage(content=_INSTRUCTIONS),
                HumanMessage(content=f"Transcript:\n\n{transcript}\n\nTitle:"),
            ]
        )
    except Exception:  # noqa: BLE001 - the fallback is the contract
        logger.warning("could not generate a chat title", exc_info=True)
        return FALLBACK_TITLE
    return clean_title(str(response.text))


def clean_title(raw: str) -> str:
    title = raw.strip().strip("\"'").strip()
    return title[:MAX_TITLE_LENGTH] or FALLBACK_TITLE
