import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from lib.config.llm_models import LLMModel
from lib.services.openai import AsyncOpenAIClient, get_openai_client
from lib.workflows.claim_substantiation.context import ContextSchema

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 300


class BaseAgent(ABC):
    """Base class with shared agent functionality.

    Agents must define these class attributes:
        - name: str
        - description: str
        - model: LLMModel
        - temperature: float
        - timeout: int = DEFAULT_LLM_TIMEOUT (optional, has default)
        - output_schema: Optional[type[BaseModel]] = None (optional)
    """

    name: str
    description: str
    model: LLMModel
    temperature: float
    timeout: int = DEFAULT_LLM_TIMEOUT
    output_schema: Optional[type[BaseModel]] = None

    @abstractmethod
    async def ainvoke(self, prompt_kwargs: dict, config: RunnableConfig = None) -> Any:
        """Invoke the agent."""
        pass


class LangChainAgent(BaseAgent):
    """Base class for agents using LangChain."""

    _llm: Optional[Any] = None

    def __init__(self, context: ContextSchema):
        self.context = context

    def create_llm(self) -> Any:
        init_kwargs = {
            "model": self.model.model_name,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }

        # For OpenAI models: use context API key if provided, otherwise fall back to env var
        # For other providers (Anthropic, Google): always use environment variables
        if (
            self.model.provider in ["openai", "azure_openai"]
            and self.context.openai_api_key
        ):
            init_kwargs["api_key"] = self.context.openai_api_key

        llm = init_chat_model(**init_kwargs)
        if self.output_schema:
            llm = llm.with_structured_output(self.output_schema)

        return llm

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = self.create_llm()
        return self._llm


class DirectOpenAIAgent(BaseAgent):
    """Base class for agents using OpenAI client directly.

    Use this for agents that need OpenAI-specific features like web search tools.
    """

    _client: Optional[AsyncOpenAIClient] = None

    def __init__(self, context: ContextSchema):
        self.context = context

    @property
    def client(self) -> AsyncOpenAIClient:
        if self._client is None:
            self._client = get_openai_client(self.context.openai_api_key)
        return self._client
