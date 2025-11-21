from __future__ import annotations

import textwrap

import pytest

from lib.agents.literature_review import (
    LiteratureReviewResponse,
    Reference,
    LiteratureReviewAgent,
)
from tests.conftest import create_test_context


class _FakeStructuredLLM:
    def __init__(self, schema):
        self._schema = schema

    def invoke(self, input=None, config=None, **kwargs):
        # Handle both positional and keyword arguments
        messages = input if input is not None else kwargs.get("messages", [])

        content = "\n".join(
            getattr(message, "content", str(message)) for message in messages
        )
        if "transformer" not in content.lower():
            raise AssertionError("Expected transformer discussion in prompt")

        reference = Reference(
            title="Attention Is All You Need",
            type="article",
            link="https://doi.org/10.48550/arXiv.1706.03762",
            bibliography_info=(
                "Vaswani, A., Shazeer, N., Parmar, N., et al. (2017). "
                "Attention Is All You Need. Advances in Neural Information Processing Systems, 30."
            ),
            related_excerpt="Transformer models rely on self-attention but this paragraph omits the seminal citation.",
            rationale=(
                "The foundational transformer paper should be cited to ground the discussion of multi-head "
                "self-attention and positional encoding."
            ),
            recommended_action="ADD_CITATION",
            explanation_for_recommended_action="Add the citation after the sentence introducing self-attention mechanisms.",
        )

        return LiteratureReviewResponse(
            relevant_references=[reference],
            rationale="Ground the transformer overview in the canonical Vaswani et al. publication.",
        )


class _FakeLLM:
    def with_structured_output(self, schema):
        return _FakeStructuredLLM(schema)

    def invoke(self, input=None, config=None, **kwargs):
        # Delegate to structured LLM behavior for consistency
        return _FakeStructuredLLM(LiteratureReviewResponse).invoke(
            input=input, config=config, **kwargs
        )

    async def ainvoke(self, input=None, config=None, **kwargs):
        # For async calls
        return self.invoke(input=input, config=config, **kwargs)

    def bind_tools(self, tools, tool_choice=None):
        # Return self when tools are bound (no-op for testing)
        return self


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    # Patch init_chat_model to return our fake LLM
    monkeypatch.setattr("lib.models.agent.init_chat_model", lambda *_, **__: _FakeLLM())

    # Also patch OpenAIWrapper in case use_direct_llm_client is True
    def fake_openai_wrapper(*args, **kwargs):
        return _FakeLLM()

    monkeypatch.setattr("lib.models.agent.OpenAIWrapper", fake_openai_wrapper)


def test_attention_paragraph_suggests_attention_is_all_you_need(monkeypatch):
    literature_review_agent = LiteratureReviewAgent(create_test_context())
    original_tools = literature_review_agent.tools
    original_use_direct_llm = literature_review_agent.use_direct_llm_client
    literature_review_agent.tools = []
    literature_review_agent.use_direct_llm_client = (
        False  # Use mocked LLM instead of OpenAIWrapper
    )

    full_document = textwrap.dedent(
        """
        ## Transformer Architectures

        Transformer-based models have defined state-of-the-art performance across language and vision tasks. The
        architecture depends heavily on self-attention to capture token interactions without recurrence. Despite
        widespread adoption, the foundational paper that introduced multi-head attention is not cited in this
        paragraph.
        """
    ).strip()

    paragraph = "Transformer designs stack self-attention blocks with positional encodings to model context efficiently."

    try:
        response = literature_review_agent.apply_sync(
            {
                "full_document": full_document,
                "bibliography": "",
                "paragraph": paragraph,
            }
        )
    finally:
        literature_review_agent.tools = original_tools
        literature_review_agent.use_direct_llm_client = original_use_direct_llm

    assert isinstance(response, LiteratureReviewResponse)
    titles = {ref.title for ref in response.relevant_references}
    assert "Attention Is All You Need" in titles

    vaswani_reference = next(
        ref
        for ref in response.relevant_references
        if ref.title == "Attention Is All You Need"
    )
    assert vaswani_reference.recommended_action == "ADD_CITATION"
    assert (
        "self-attention" in vaswani_reference.explanation_for_recommended_action.lower()
    )
