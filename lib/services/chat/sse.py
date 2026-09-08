"""Server-sent events for a chat turn: heartbeats, cancellation, and a time cap.

Three facts of the deployment shape this, all checked before it was written:

- **Detection of a gone client is write-driven.** uvicorn only learns a peer has
  left when the connection closes, and a client that merely stops reading is
  invisible until the server writes. A heartbeat every few seconds bounds how
  long an abandoned turn keeps spending tokens.
- **Railway closes a response after 5 minutes with no bytes, and after 15
  minutes regardless.** The heartbeat covers the first; the turn cap ends a
  run cleanly before the proxy cuts it.
- **The graph has to run in a task this generator owns.** Cancelling a
  generator that is merely awaiting the graph does stop it; but a heartbeat
  loop that races the graph against a timer leaks the graph unless the loop
  cancels it explicitly, so this one does, in ``finally``.

SSE rather than newline-delimited JSON because the app's gzip middleware buffers
every other streamed content type inside zlib until enough output accumulates,
which would hold back both the deltas and the heartbeats. ``text/event-stream``
is the one type it leaves alone.
"""

import asyncio
import json
import logging
from contextlib import suppress
from typing import AsyncGenerator, AsyncIterator

from lib.services.chat.events import ChatEvent, error_event

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
# Railway's ceiling is 15 minutes; end the turn ourselves with a minute to spare.
TURN_TIMEOUT_SECONDS = 14 * 60.0

HEARTBEAT = ": ping\n\n"
TIMEOUT_MESSAGE = "This turn ran past the time limit and was stopped."

_DONE = object()


def encode_event(event: ChatEvent) -> str:
    """One SSE ``data:`` frame. ``default=str`` keeps an odd tool result from
    taking the whole stream down."""

    return f"data: {json.dumps(event, default=str)}\n\n"


async def sse_stream(
    events: AsyncIterator[ChatEvent],
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
    turn_timeout_seconds: float = TURN_TIMEOUT_SECONDS,
) -> AsyncGenerator[str, None]:
    """Encode ``events`` as SSE, with heartbeats while the producer is quiet.

    A producer failure or timeout becomes an ``error`` event and ends the stream;
    the HTTP status is already 200 by then, so the event is the only channel.
    """

    queue: asyncio.Queue[object] = asyncio.Queue()

    async def produce() -> None:
        try:
            async with asyncio.timeout(turn_timeout_seconds):
                async for event in events:
                    queue.put_nowait(event)
        except TimeoutError:
            queue.put_nowait(error_event(TIMEOUT_MESSAGE))
        except Exception as error:  # noqa: BLE001 - reported to the client as an event
            logger.exception("chat turn failed")
            queue.put_nowait(error_event(str(error) or "The turn failed."))
        finally:
            queue.put_nowait(_DONE)

    producer = asyncio.create_task(produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield HEARTBEAT
                continue
            if item is _DONE:
                return
            yield encode_event(item)  # type: ignore[arg-type]  # only ChatEvents are queued
    finally:
        if not producer.done():
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer
