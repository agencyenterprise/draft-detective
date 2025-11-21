from typing import Literal
from pydantic import BaseModel
from lib.config.env import config


class LLMModel(BaseModel):
    name: str
    provider: str

    @property
    def model_name(self) -> str:
        """For usage with LangChain's init_chat_model"""

        return f"{self.provider}:{self.name}"

    def __str__(self) -> str:
        return self.model_name


def get_openai_provider() -> Literal["openai", "azure_openai"]:
    if config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT:
        return "azure_openai"
    else:
        return "openai"


# OpenAI models
gpt_5_model = LLMModel(provider=get_openai_provider(), name="gpt-5")
gpt_5_mini_model = LLMModel(provider=get_openai_provider(), name="gpt-5-mini")
gpt_5_1_model = LLMModel(provider=get_openai_provider(), name="gpt-5.1")
gpt_4_1_model = LLMModel(provider=get_openai_provider(), name="gpt-4.1")

# Anthropic models
claude_3_5_sonnet_model = LLMModel(
    provider="anthropic", name="claude-sonnet-4-5-20250929"
)

# Google models
gemini_2_flash_model = LLMModel(provider="google_genai", name="gemini-2.5-flash-lite")
