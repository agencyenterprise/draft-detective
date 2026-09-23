"""Tests for the per-chunk abbreviation extractor, without invoking the LLM."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from langchain.agents.structured_output import StructuredOutputValidationError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from lib.agents import abbreviation_chunk_extractor
from lib.agents.abbreviation_chunk_extractor import (
    CHUNK_GUIDANCE,
    RECURSION_LIMIT,
    AbbreviationChunkExtractorAgent,
    PartialChunkExtractionError,
    build_messages,
)
from lib.skills import load_skill_prompt
from lib.workflows.abbreviation_scan_v2.chunk_models import (
    ChunkExtractionResult,
    ChunkOccurrence,
)

MARKDOWN = "\n".join(f"line {n}" for n in range(1, 401))
KWARGS: dict[str, Any] = {"markdown": MARKDOWN, "start_line": 10, "end_line": 42}


def _agent(monkeypatch, invoke) -> tuple[AbbreviationChunkExtractorAgent, dict]:
    """The extractor with `create_deep_agent` replaced by a stub running `invoke`."""
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured["create"] = kwargs

        class _DeepAgent:
            async def ainvoke(self, payload, config=None):
                captured["payload"], captured["config"] = payload, config
                return await invoke(payload)

        return _DeepAgent()

    monkeypatch.setattr(abbreviation_chunk_extractor, "create_deep_agent", fake_create_deep_agent)
    agent = AbbreviationChunkExtractorAgent(SimpleNamespace(openai_api_key=None))  # type: ignore[arg-type]
    agent._llm = object()  # type: ignore[assignment]
    return agent, captured


def test_system_prompt_is_the_skill_plus_static_guidance_and_the_range_goes_in_the_message():
    system, human = build_messages(KWARGS)
    assert isinstance(system, SystemMessage) and isinstance(human, HumanMessage)
    assert system.content == load_skill_prompt("abbreviation-extraction") + CHUNK_GUIDANCE
    assert str(human.content) == (
        "Catalogue the abbreviations on lines 10-42 of /main.md (the document has 400 lines)."
    )


def test_guidance_leaves_position_rules_to_the_agent_and_document_wide_fields_to_the_merge():
    assert "/main.md" in CHUNK_GUIDANCE and "read_file" in CHUNK_GUIDANCE
    assert "References" in CHUNK_GUIDANCE and "cover page" in CHUNK_GUIDANCE
    for field in ("abbr", "inline_definition", "line_start", "line_end", "ignored", "ignored_reason"):
        assert f"`{field}`" in CHUNK_GUIDANCE
    assert "`occurrence_number`" not in CHUNK_GUIDANCE
    assert "`abbreviations_section_definition`" not in CHUNK_GUIDANCE


@pytest.mark.asyncio
async def test_document_is_mounted_and_the_full_conversation_is_returned(monkeypatch):
    found = ChunkExtractionResult(occurrences=[ChunkOccurrence(abbr="NATO", line_start=12, line_end=12)])

    async def invoke(payload):
        return {"structured_response": found, "messages": [*payload["messages"], AIMessage(content="{}")]}

    agent, captured = _agent(monkeypatch, invoke)
    result, messages = await agent.ainvoke(KWARGS)

    assert result is found
    assert list(captured["payload"]["files"]) == ["/main.md"]
    assert captured["payload"]["files"]["/main.md"]["content"] == MARKDOWN.split("\n")
    assert captured["config"]["recursion_limit"] == RECURSION_LIMIT
    assert captured["create"]["response_format"].schema is ChunkExtractionResult
    # The full conversation is kept, system prompt included, so a run can be reconstructed.
    assert isinstance(messages[0], SystemMessage)
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_truncated_response_raises_partial_with_the_salvaged_occurrences(monkeypatch):
    complete = {"abbr": "NATO", "inline_definition": "", "line_start": 12, "line_end": 12, "ignored": False, "ignored_reason": None}
    cut = AIMessage(content='{"occurrences": [' + json.dumps(complete) + ', {"abbr": "EU", "inl')

    async def invoke(payload):
        raise StructuredOutputValidationError("ChunkExtractionResult", ValueError("cut"), cut)

    agent, _ = _agent(monkeypatch, invoke)
    with pytest.raises(PartialChunkExtractionError) as excinfo:
        await agent.ainvoke(KWARGS)

    assert [o.abbr for o in excinfo.value.result.occurrences] == ["NATO"]
    assert [type(m) for m in excinfo.value.messages] == [SystemMessage, HumanMessage, AIMessage]
    assert excinfo.value.messages[-1] is cut


@pytest.mark.asyncio
async def test_unsalvageable_structured_output_error_is_reraised(monkeypatch):
    async def invoke(payload):
        raise StructuredOutputValidationError("ChunkExtractionResult", ValueError("bad"), AIMessage(content="nope"))

    agent, _ = _agent(monkeypatch, invoke)
    with pytest.raises(StructuredOutputValidationError):
        await agent.ainvoke(KWARGS)
