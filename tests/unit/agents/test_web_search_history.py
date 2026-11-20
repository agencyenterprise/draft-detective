"""A failed web search in the history must not fail every later model call."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from lib.agents.web_search_history import repair_web_search_history


def _search(args: dict | None) -> AIMessage:
    call: dict = {"type": "server_tool_call", "name": "web_search", "id": "ws_1"}
    if args is not None:
        call["args"] = args
    return AIMessage(
        content=[
            call,
            {"type": "server_tool_result", "tool_call_id": "ws_1", "status": "success"},
            {"type": "text", "text": "Nothing new."},
        ],
        response_metadata={"model_provider": "openai"},
    )


def _web_search_items(messages: list[AnyMessage]) -> list[dict]:
    """The web-search items of the request langchain-openai would send."""

    llm = ChatOpenAI(
        model="gpt-5.6-sol",
        api_key=SecretStr("test"),
        use_responses_api=True,
        output_version="v1",
    )
    payload = llm._get_request_payload(messages)
    return [i for i in payload["input"] if i.get("type") == "web_search_call"]


def test_a_search_without_an_action_no_longer_sends_an_empty_one() -> None:
    messages: list[AnyMessage] = [HumanMessage("go"), _search({}), HumanMessage("on")]
    # The bug: OpenAI refuses this with "Missing required parameter: action.type".
    assert _web_search_items(messages)[0]["action"] == {}

    (item,) = _web_search_items(repair_web_search_history(messages))
    assert "action" not in item
    assert item["status"] == "completed"


def test_a_search_with_an_action_is_left_alone() -> None:
    action = {"type": "search", "query": "office vacancy 2026"}
    messages: list[AnyMessage] = [HumanMessage("go"), _search(action)]

    assert repair_web_search_history(messages)[1] is messages[1]
    assert _web_search_items(repair_web_search_history(messages))[0]["action"] == action


def test_openai_native_blocks_are_repaired_too() -> None:
    message = AIMessage(
        content=[{"type": "web_search_call", "id": "ws_1", "action": {"query": "x"}}]
    )

    (repaired,) = repair_web_search_history([message])

    assert repaired.content == [{"type": "web_search_call", "id": "ws_1"}]
    # The state's copy is untouched: only the request is fixed.
    assert message.content[0]["action"] == {"query": "x"}  # type: ignore[index]
