import hashlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Literal, Optional, TypedDict

from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from lib.config.llm_models import LLMModel
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 300


class ReasoningDict(TypedDict):
    effort: Literal["low", "medium", "high"]
    summary: Literal["auto"]


class BaseAgent(ABC):
    """Base class with shared agent functionality.

    Agents must define these class attributes:
        - name: str
        - description: str
        - model: LLMModel
        - temperature: float
        - timeout: int = DEFAULT_LLM_TIMEOUT (optional, has default)
        - output_schema: Optional[type[BaseModel]] = None (optional)
        - reasoning: Optional[ReasoningDict] = None (optional, should be for example: {"effort": "low", "summary": "auto"})
    """

    name: str
    description: str
    model: LLMModel
    temperature: float
    timeout: int = DEFAULT_LLM_TIMEOUT
    reasoning: Optional[ReasoningDict] = None
    output_schema: Optional[type[BaseModel]] = None

    @abstractmethod
    async def ainvoke(
        self, prompt_kwargs: dict, config: Optional[RunnableConfig] = None
    ) -> Any:
        """Invoke the agent."""
        pass


class LangChainAgent(BaseAgent):
    """Base class for agents using LangChain."""

    _llm: Optional[BaseChatModel] = None

    def __init__(self, context: ContextSchema):
        self.context = context

    def get_rate_limiter(self) -> InMemoryRateLimiter:
        api_key = self.context.openai_api_key or "default"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return get_rate_limiter(key_hash)

    def get_init_chat_model_kwargs(self) -> dict:
        init_kwargs = {
            "model": self.model.model_name,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "rate_limiter": self.get_rate_limiter(),
        }

        if self.reasoning:
            init_kwargs["reasoning"] = self.reasoning

        # For OpenAI models: use context API key if provided, otherwise fall back to env var
        # For other providers (Anthropic, Google): always use environment variables
        if (
            self.model.provider in ["openai", "azure_openai"]
            and self.context.openai_api_key
        ):
            init_kwargs["api_key"] = self.context.openai_api_key

        return init_kwargs

    def create_llm(self) -> BaseChatModel:
        init_kwargs = self.get_init_chat_model_kwargs()

        llm = init_chat_model(**init_kwargs)
        if self.output_schema:
            llm = llm.with_structured_output(self.output_schema)

        return llm

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = self.create_llm()
        return self._llm


@lru_cache(maxsize=256)
def get_rate_limiter(api_key_hash: str) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        requests_per_second=64,  # How many requests per second are allowed
        check_every_n_seconds=0.2,  # Wake up every X seconds to check whether allowed to make a request
        max_bucket_size=200,  # Controls the maximum burst size
    )
