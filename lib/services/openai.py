import logging
from asyncio import sleep
from time import monotonic
from typing import TypeVar

from langfuse.openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.responses import ParsedResponse
from pydantic import BaseModel

from lib.config.env import config

logger = logging.getLogger(__name__)


ResponseFormatT = TypeVar("ResponseFormatT")


def get_openai_client() -> AsyncOpenAI:
    if config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT:
        return AsyncAzureOpenAI()
    else:
        return AsyncOpenAI()


async def wait_for_response(
    client: AsyncOpenAI,
    response: ParsedResponse[ResponseFormatT],
    poll_interval_seconds: int = 20,
    log_info: str = "",
) -> ParsedResponse[ResponseFormatT]:
    start_time = monotonic()

    while response.status in {"queued", "in_progress"}:
        await sleep(poll_interval_seconds)
        response = await client.responses.retrieve(response.id)
        elapsed = monotonic() - start_time
        logger.info(
            "Call id: %s => Current status: %s... Running for %.1fs. Checking back in %s seconds %s",
            response.id,
            response.status,
            elapsed,
            poll_interval_seconds,
            log_info,
        )

    return response


def ensure_structured_output_response(
    response: ParsedResponse[ResponseFormatT], schema: type[BaseModel]
) -> BaseModel:
    """Return a Pydantic instance from an OpenAI Responses API ParsedResponse.

    - If `response.output_parsed` is a Pydantic model, return it.
    - Else if `response.output_parsed` is a dict, validate via `schema.model_validate`.
    - Else if `response.output_text` is present, parse JSON via `schema.model_validate_json`.
    - Else if `response.output` is a dict, validate via `schema.model_validate`.
    - Otherwise, raise ValueError.
    """
    if response.status != "completed":
        raise Exception(
            f"Response ({response.id}) failed: {response.status} - {response.error.message} ({response.error})"
        )

    if hasattr(response, "output_parsed"):
        op = getattr(response, "output_parsed")
        if isinstance(op, BaseModel):
            return op
        if isinstance(op, dict):
            return schema.model_validate(op)

    if hasattr(response, "output_text") and isinstance(response.output_text, str):
        return schema.model_validate_json(response.output_text)

    if hasattr(response, "output") and isinstance(response.output, dict):
        return schema.model_validate(response.output)

    raise ValueError("Response did not include a structured result.")
