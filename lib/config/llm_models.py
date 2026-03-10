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
gpt_5_model = LLMModel(provider="openai", name="gpt-5")
gpt_5_mini_model = LLMModel(provider="openai", name="gpt-5-mini")
gpt_5_1_model = LLMModel(provider="openai", name="gpt-5.1")
gpt_4_1_model = LLMModel(provider="openai", name="gpt-4.1")
gpt_5_2_model = LLMModel(provider="openai", name="gpt-5.2")
gpt_5_4_model = LLMModel(provider="openai", name="gpt-5.4")

# Anthropic models
claude_3_5_sonnet_model = LLMModel(
    provider="anthropic", name="claude-sonnet-4-5-20250929"
)

# Google models
gemini_2_flash_model = LLMModel(provider="google_genai", name="gemini-2.5-flash-lite")


# Registry of all available models for testing and comparison
# Key: model.name, Value: model instance
ALL_MODELS = {
    "gpt-5": gpt_5_model,
    "gpt-5-mini": gpt_5_mini_model,
    "gpt-5.1": gpt_5_1_model,
    "gpt-5.2": gpt_5_2_model,
    "gpt-4.1": gpt_4_1_model,
    "gpt-5.4": gpt_5_4_model,
    "claude-sonnet-4-5-20250929": claude_3_5_sonnet_model,
    "gemini-2.5-flash-lite": gemini_2_flash_model,
}
