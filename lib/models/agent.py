import logging
from abc import ABC, abstractmethod
from typing import Any, Literal, Optional, TypedDict

from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.rate_limiters import BaseRateLimiter
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel

from lib.config.env import get_model_api_key
from lib.config.llm_models import LLMModel
from lib.config.rate_limiter import get_rate_limiter, hash_api_key
from lib.workflows.context import ContextSchema

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 240
DEFAULT_LLM_MAX_RETRIES = 4


class ReasoningDict(TypedDict):
    effort: Literal["low", "medium", "high"]
    summary: Literal["auto", "concise", "detailed"]


class BaseAgent(ABC):
    """Base class with shared agent functionality.

    Agents must define these class attributes:
        - name: str
        - description: str
        - model: LLMModel
        - timeout: int = DEFAULT_LLM_TIMEOUT (optional, has default)
        - max_retries: int = DEFAULT_LLM_MAX_RETRIES (optional, has default)
        - output_schema: Optional[type[BaseModel]] = None (optional)
        - reasoning: Optional[ReasoningDict] = None (optional, should be for example: {"effort": "low", "summary": "auto"})
    """

    name: str
    description: str
    model: LLMModel
    timeout: int = DEFAULT_LLM_TIMEOUT
    max_retries: int = DEFAULT_LLM_MAX_RETRIES
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
        # Shadows the class-level model for this instance only, when the run
        # names one (an eval comparing models on the same pipeline).
        self.model = context.agent_model(self.model)

    def _resolve_api_key(self) -> str | None:
        """User context key wins; falls back to per-model override. OpenAI only."""
        if self.model.provider != "openai":
            return None
        return self.context.openai_api_key or get_model_api_key(self.model.name)

    def get_rate_limiter(self) -> BaseRateLimiter:
        return get_rate_limiter(hash_api_key(self._resolve_api_key() or "default"))

    def get_init_chat_model_kwargs(self) -> dict:
        init_kwargs = {
            "model": self.model.model_name,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "rate_limiter": self.get_rate_limiter(),
            **self._generation_kwargs(),
        }

        api_key = self._resolve_api_key()
        if api_key:
            init_kwargs["api_key"] = api_key

        return init_kwargs

    def _generation_kwargs(self) -> dict[str, Any]:
        """The agent's reasoning effort, in the terms its provider takes.

        OpenAI takes it as `reasoning`; Claude as adaptive thinking plus `effort`.
        Other providers run without it. No `temperature` is set anywhere: the
        reasoning models the agents run on reject it.
        """
        provider = self.model.provider
        if provider == "openai":
            return {"reasoning": self.reasoning} if self.reasoning else {}
        if provider == "anthropic":
            if not self.reasoning:
                return {}
            return {
                "thinking": {"type": "adaptive", "display": "summarized"},
                "effort": self.reasoning["effort"],
            }
        return {}

    def create_llm(self) -> BaseChatModel:
        init_kwargs = self.get_init_chat_model_kwargs()

        llm = init_chat_model(**init_kwargs)
        if self.output_schema:
            # Claude's default is a forced tool call, which does not hold it to the
            # schema: it returned a nested object as a JSON string. Its native
            # structured output does. OpenAI's default already is that.
            if self.model.provider == "anthropic":
                llm = llm.with_structured_output(self.output_schema, method="json_schema")
            else:
                llm = llm.with_structured_output(self.output_schema)

        return llm

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = self.create_llm()
        return self._llm

