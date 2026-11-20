"""The OpenAI key in a gateway's own header, when ``OPENAI_API_KEY_HEADER`` names one.

LangChain models get the header through their HTTP clients, not ``default_headers``:
LangChain serializes a model's ``default_headers`` unredacted into the payload every
callback (Langfuse included) receives, while it leaves the HTTP clients out.
"""

from functools import lru_cache
from typing import Any

import openai

from lib.config.env import config


def openai_key_header(api_key: str | None) -> dict[str, str]:
    """The header carrying ``api_key`` (or the server's key). Empty when unset."""

    key = api_key or config.OPENAI_API_KEY
    if not config.OPENAI_API_KEY_HEADER or not key:
        return {}
    return {config.OPENAI_API_KEY_HEADER: key}


def openai_http_client_kwargs(api_key: str | None) -> dict[str, Any]:
    """``http_client`` and ``http_async_client`` for a LangChain OpenAI model or
    embeddings, sending the key header. Empty when there is none to send."""

    header = openai_key_header(api_key)
    if not header:
        return {}
    ((name, value),) = header.items()
    return {
        "http_client": _sync_client(name, value),
        "http_async_client": _async_client(name, value),
    }


# One client per key, as LangChain caches its own defaults: a client per model would
# open a new connection pool for every call.
@lru_cache(maxsize=32)
def _sync_client(name: str, value: str) -> openai.DefaultHttpxClient:
    return openai.DefaultHttpxClient(headers={name: value})


@lru_cache(maxsize=32)
def _async_client(name: str, value: str) -> openai.DefaultAsyncHttpxClient:
    return openai.DefaultAsyncHttpxClient(headers={name: value})
