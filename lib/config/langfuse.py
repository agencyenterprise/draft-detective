from typing import Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from lib.config.env import config


class NoOpCallbackHandler(BaseCallbackHandler):
    """A callback handler that does nothing.

    Used when Langfuse is not configured, allowing the rest of the system
    to work without tracing.
    """

    pass


def _is_langfuse_configured() -> bool:
    """Check if required Langfuse configuration is present."""
    return all(
        [
            config.LANGFUSE_SECRET_KEY,
            config.LANGFUSE_PUBLIC_KEY,
            config.LANGFUSE_HOST,
        ]
    )


# Initialize Langfuse client and handler based on configuration
langfuse: Optional[Langfuse] = None
langfuse_handler: BaseCallbackHandler

if _is_langfuse_configured():
    langfuse = Langfuse(
        secret_key=config.LANGFUSE_SECRET_KEY,
        public_key=config.LANGFUSE_PUBLIC_KEY,
        host=config.LANGFUSE_HOST,
        timeout=120,  # Extended timeout to 120 seconds for large payloads
        flush_at=100,  # Batch up to 100 traces before sending
        flush_interval=10,  # Send batches every 10 seconds
    )
    langfuse_handler = CallbackHandler()
else:
    langfuse_handler = NoOpCallbackHandler()
