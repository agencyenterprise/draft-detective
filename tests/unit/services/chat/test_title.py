"""Thread titles: the model call, its input shape, and the fallback contract."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from lib.services.chat import title as title_module
from lib.services.chat.messages import ChatTurnMessage
from lib.services.chat.title import FALLBACK_TITLE, TITLE_MODEL, generate_title

MESSAGES = [
    ChatTurnMessage(role="user", content="Check my references for APA style"),
    ChatTurnMessage(role="assistant", content="Paste them here."),
    ChatTurnMessage(role="user", content="   "),
]


def _llm(reply: str | Exception) -> SimpleNamespace:
    ainvoke = AsyncMock(side_effect=reply) if isinstance(reply, Exception) else AsyncMock(
        return_value=SimpleNamespace(text=reply)
    )
    return SimpleNamespace(ainvoke=ainvoke)


class TestGenerateTitle:
    @pytest.mark.asyncio
    async def test_the_transcript_travels_as_one_message_under_the_instruction(self) -> None:
        """Replaying the turns makes a reasoning model answer the last one instead
        of naming the conversation, so the transcript goes in a single message."""
        llm = _llm(' "APA Reference Check" ')
        with patch.object(title_module, "init_chat_model", return_value=llm) as init:
            result = await generate_title(MESSAGES, api_key="sk-user")

        assert result == "APA Reference Check"

        kwargs = init.call_args.kwargs
        assert kwargs["model"] == TITLE_MODEL.model_name
        assert kwargs["api_key"] == "sk-user"
        assert "temperature" not in kwargs  # reasoning models reject it

        (prompt,), _ = llm.ainvoke.call_args
        assert [type(m) for m in prompt] == [SystemMessage, HumanMessage]
        transcript = prompt[1].content
        assert "user: Check my references for APA style" in transcript
        assert "assistant: Paste them here." in transcript
        assert "user:    " not in transcript  # blank turns are dropped

    @pytest.mark.asyncio
    async def test_the_server_key_is_used_when_the_user_has_none(self) -> None:
        with (
            patch.object(title_module, "init_chat_model", return_value=_llm("Title")) as init,
            patch.object(title_module, "get_model_api_key", return_value="sk-server"),
        ):
            await generate_title(MESSAGES, api_key=None)
        assert init.call_args.kwargs["api_key"] == "sk-server"

    @pytest.mark.asyncio
    async def test_a_model_failure_yields_the_fallback(self) -> None:
        with patch.object(
            title_module, "init_chat_model", return_value=_llm(RuntimeError("rate limited"))
        ):
            assert await generate_title(MESSAGES) == FALLBACK_TITLE

    @pytest.mark.asyncio
    async def test_an_empty_reply_yields_the_fallback(self) -> None:
        with patch.object(title_module, "init_chat_model", return_value=_llm("  ")):
            assert await generate_title(MESSAGES) == FALLBACK_TITLE
