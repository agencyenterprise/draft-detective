from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

EMBEDDING_MODEL_LARGE = "text-embedding-3-large"


def init_embeddings(
    model: str = EMBEDDING_MODEL_LARGE,
    api_key: str | None = None,
) -> OpenAIEmbeddings:
    """Common builder for OpenAIEmbeddings."""

    kwargs: dict = {"model": model}

    if api_key:
        kwargs["api_key"] = api_key

    return OpenAIEmbeddings(**kwargs)


class LLMModel(BaseModel):
    name: str
    provider: str

    @property
    def model_name(self) -> str:
        """For usage with LangChain's init_chat_model"""

        if not self.provider:
            return self.name

        return f"{self.provider}:{self.name}"

    def __str__(self) -> str:
        return self.model_name

    def get_model_name_for_inspectai(self) -> str:
        """For usage with InspectAI's GenerateConfig"""

        return self.model_name.replace(":", "/")

    @staticmethod
    def from_inspectai_name(inspectai_name: str) -> "LLMModel":
        """Create an LLMModel from an InspectAI model name (e.g. 'openai/gpt-5.2')."""
        if "/" in inspectai_name:
            provider, name = inspectai_name.split("/", 1)
        else:
            provider, name = "", inspectai_name
        return LLMModel(provider=provider, name=name)


# OpenAI models
#
# Every agent runs on gpt-5.6-terra. It replaced the gpt-5.4-mini / gpt-5.4 /
# gpt-5.5 tiers on 28 Aug 2026, after a comparison found it flat against all three
# on 17 of 18 evals at roughly half the premium tier's cost. `figures_tables_check`
# is the one eval it scores below the old stack on. The superseded numbers are kept
# in `docs/eval-scores-gpt-5.4-5.5.md`.
gpt_5_6_terra_model = LLMModel(provider="openai", name="gpt-5.6-terra")
# Sibling tiers of the same generation. Not used by any workflow; offered in the
# /chat model picker so a reviewer can compare them on a real question.
gpt_5_6_luna_model = LLMModel(provider="openai", name="gpt-5.6-luna")
gpt_5_6_sol_model = LLMModel(provider="openai", name="gpt-5.6-sol")
gpt_4_1_model = LLMModel(provider="openai", name="gpt-4.1")

# Anthropic models
claude_3_5_sonnet_model = LLMModel(
    provider="anthropic", name="claude-sonnet-4-5-20250929"
)

# Google models
gemini_2_flash_model = LLMModel(provider="google_genai", name="gemini-2.5-flash-lite")


# Registry of all available models for testing and comparison
# Key: model.name, Value: model instance
ALL_MODELS = {
    "gpt-4.1": gpt_4_1_model,
    "gpt-5.6-terra": gpt_5_6_terra_model,
    "gpt-5.6-luna": gpt_5_6_luna_model,
    "gpt-5.6-sol": gpt_5_6_sol_model,
    "claude-sonnet-4-5-20250929": claude_3_5_sonnet_model,
    "gemini-2.5-flash-lite": gemini_2_flash_model,
}


# Server-side web search is declared differently per provider: OpenAI's Responses API
# takes a bare {"type": "web_search"}, while Anthropic needs a dated tool type and a
# name. Passing the OpenAI shape to a Claude model raises KeyError('function') inside
# LangChain's tool conversion, so the declaration has to follow the model. Build it
# through this helper rather than writing the dict at the call site.
def web_search_tool(model: LLMModel) -> dict:
    """The server-side web-search tool declaration this model understands."""

    if model.provider != "anthropic":
        return {"type": "web_search"}
    # Deliberately the basic variant even on models that support the newer
    # web_search_20260209. That one performs dynamic filtering by running code
    # execution internally, and LangChain does not round-trip the resulting
    # `code_execution` blocks: the next turn is rejected with "code_execution tool use
    # ... found without a corresponding code_execution_tool_result block". The basic
    # variant returns only web_search blocks, which LangChain handles.
    return {"type": "web_search_20250305", "name": "web_search"}
