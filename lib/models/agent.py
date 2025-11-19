import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.runnables.config import RunnableConfig
from langfuse.openai import AsyncOpenAI
from pydantic import BaseModel, Field

from lib.config.llm_models import LLMModel
from lib.services.openai import get_openai_client

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 300


class AgentConfig(BaseModel):
    """Shared configuration for all agents."""

    model_config = {"arbitrary_types_allowed": True}

    model: LLMModel
    temperature: float
    timeout: int = Field(default=DEFAULT_LLM_TIMEOUT)
    output_schema: Optional[type[BaseModel]] = Field(default=None)


class BaseAgent(ABC):
    """Base class with shared agent functionality.

    Agents must define these class attributes:
        - name: str
        - description: str
        - model: LLMModel
        - temperature: float
        - schema: Optional[type[BaseModel]] = None
    """

    name: str
    description: str

    def __init__(
        self,
        model: Optional[LLMModel] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
    ):
        self.config = AgentConfig(
            model=model if model is not None else self.__class__.model,
            temperature=(
                temperature if temperature is not None else self.__class__.temperature
            ),
            timeout=timeout or DEFAULT_LLM_TIMEOUT,
            output_schema=getattr(self.__class__, "schema", None),
        )

    @abstractmethod
    async def ainvoke(self, prompt_kwargs: dict, config: RunnableConfig = None) -> Any:
        """Invoke the agent."""
        pass


class LangChainAgent(BaseAgent):
    """Base class for agents using LangChain."""

    _llm: Optional[Any] = None

    @property
    def llm(self) -> Any:
        if self._llm is None:
            llm = init_chat_model(
                self.config.model.model_name,
                temperature=self.config.temperature,
                timeout=self.config.timeout,
            )
            if self.config.output_schema:
                llm = llm.with_structured_output(self.config.output_schema)
            self._llm = llm
        return self._llm


class DirectOpenAIAgent(BaseAgent):
    """Base class for agents using OpenAI client directly.

    Use this for agents that need OpenAI-specific features like web search tools.
    """

    _client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = get_openai_client()
        return self._client


class QCResult(BaseModel):
    valid: bool
    feedback: str
