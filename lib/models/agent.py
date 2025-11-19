import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.runnables.config import RunnableConfig
from langfuse.openai import AsyncOpenAI
from pydantic import BaseModel

from lib.config.llm_models import LLMModel
from lib.services.openai import get_openai_client

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 300


class BaseAgent(ABC):
    """Base class with shared agent functionality.

    Agents must define these class attributes:
        - name: str
        - description: str
        - model: LLMModel
        - temperature: float
        - output_schema: Optional[type[BaseModel]] = None
    """

    name: str
    description: str
    model: LLMModel
    temperature: float
    timeout: int
    output_schema: Optional[type[BaseModel]]

    def __init__(
        self,
        model: Optional[LLMModel] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
    ):
        self.model = model if model is not None else self.__class__.model
        self.temperature = (
            temperature if temperature is not None else self.__class__.temperature
        )
        self.timeout = timeout or DEFAULT_LLM_TIMEOUT
        self.output_schema = getattr(self.__class__, "schema", None)

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
                self.model.model_name,
                temperature=self.temperature,
                timeout=self.timeout,
            )
            if self.output_schema:
                llm = llm.with_structured_output(self.output_schema)
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
