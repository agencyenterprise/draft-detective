import logging
from typing import Optional, Union

from openai import AsyncAzureOpenAI as StandardAsyncAzureOpenAI
from openai import AsyncOpenAI as StandardAsyncOpenAI

from lib.config.env import config
from lib.config.langfuse import langfuse

logger = logging.getLogger(__name__)

AsyncOpenAIClient = Union[StandardAsyncOpenAI, StandardAsyncAzureOpenAI]


def _is_using_azure() -> bool:
    """Check if Azure OpenAI is configured."""
    return bool(config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT)


def get_openai_client(api_key: Optional[str] = None) -> AsyncOpenAIClient:
    """Get an OpenAI client, with Langfuse instrumentation if configured."""
    use_azure = _is_using_azure()

    if langfuse is not None:
        from langfuse.openai import AsyncAzureOpenAI, AsyncOpenAI

        return AsyncAzureOpenAI() if use_azure else AsyncOpenAI(api_key=api_key)

    return (
        StandardAsyncAzureOpenAI()
        if use_azure
        else StandardAsyncOpenAI(api_key=api_key)
    )
