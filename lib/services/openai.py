import logging
from asyncio import sleep
from time import monotonic
from typing import Optional, TypeVar, Union

from openai import AsyncAzureOpenAI as StandardAsyncAzureOpenAI
from openai import AsyncOpenAI as StandardAsyncOpenAI
from openai.types.responses import ParsedResponse
from pydantic import BaseModel

from lib.config.env import config
from lib.config.langfuse import langfuse

logger = logging.getLogger(__name__)

ResponseFormatT = TypeVar("ResponseFormatT")
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


def ensure_structured_output_response(
    response: ParsedResponse[ResponseFormatT], schema: type[BaseModel]
) -> BaseModel:
    """Parse structured output from an OpenAI Responses API ParsedResponse."""
    if response.status != "completed":
        raise ValueError(
            f"Response ({response.id}) failed: {response.status} - {response.error}"
        )

    # Try parsed output first (preferred)
    output = getattr(response, "output_parsed", None)
    if isinstance(output, BaseModel):
        return output
    if isinstance(output, dict):
        return schema.model_validate(output)

    # Fallback to text/raw output
    if text := getattr(response, "output_text", None):
        return schema.model_validate_json(text)
    if isinstance(getattr(response, "output", None), dict):
        return schema.model_validate(response.output)

    raise ValueError("Response did not include a structured result.")
