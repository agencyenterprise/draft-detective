"""Heartbeats, cancellation and the time cap of the chat event stream.

These pin the behaviours the deployment depends on (see ``lib/services/chat/sse.py``):
a quiet producer still produces bytes, a consumer that stops reading stops the
producer, and a producer that fails or overruns ends the stream with an error
event rather than a dropped connection.
"""

import asyncio
import json
from typing import AsyncIterator

import pytest

from lib.services.chat.events import ChatEvent
from lib.services.chat.sse import HEARTBEAT, TIMEOUT_MESSAGE, encode_event, sse_stream


def _decode(frame: str) -> ChatEvent:
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    return json.loads(frame[len("data: ") : -2])


async def _events(*events: ChatEvent, delay: float = 0.0) -> AsyncIterator[ChatEvent]:
    for event in events:
        if delay:
            await asyncio.sleep(delay)
        yield event


class TestEncoding:
    def test_a_frame_is_one_data_line(self) -> None:
        assert encode_event({"t": "text", "v": "hi"}) == 'data: {"t": "text", "v": "hi"}\n\n'

    def test_unserialisable_values_are_stringified_rather_than_fatal(self) -> None:
        frame = encode_event({"t": "tool_result", "id": "c", "result": {1, 2}})
        assert _decode(frame)["result"] in ("{1, 2}", "{2, 1}")


@pytest.mark.asyncio
class TestStreaming:
    async def test_events_pass_through_in_order(self) -> None:
        frames = [
            frame
            async for frame in sse_stream(
                _events({"t": "text", "v": "a"}, {"t": "text", "v": "b"})
            )
        ]
        assert [_decode(frame)["v"] for frame in frames] == ["a", "b"]

    async def test_a_quiet_producer_still_yields_heartbeats(self) -> None:
        frames = [
            frame
            async for frame in sse_stream(
                _events({"t": "text", "v": "late"}, delay=0.25),
                heartbeat_seconds=0.05,
            )
        ]
        assert frames.count(HEARTBEAT) >= 2
        assert _decode(frames[-1]) == {"t": "text", "v": "late"}

    async def test_a_consumer_that_stops_reading_cancels_the_producer(self) -> None:
        cancelled = asyncio.Event()

        async def producer() -> AsyncIterator[ChatEvent]:
            try:
                yield {"t": "text", "v": "first"}
                await asyncio.sleep(10)
                yield {"t": "text", "v": "never"}
            except asyncio.CancelledError:
                cancelled.set()
                raise

        stream = sse_stream(producer(), heartbeat_seconds=0.05)
        assert _decode(await anext(stream))["v"] == "first"
        await stream.aclose()
        await asyncio.wait_for(cancelled.wait(), timeout=1)

    async def test_a_failing_producer_ends_with_an_error_event(self) -> None:
        async def producer() -> AsyncIterator[ChatEvent]:
            yield {"t": "text", "v": "partial"}
            raise RuntimeError("model unavailable")

        frames = [frame async for frame in sse_stream(producer())]
        assert _decode(frames[-1]) == {"t": "error", "v": "model unavailable"}

    async def test_an_overrunning_turn_is_stopped_with_an_error_event(self) -> None:
        stopped = asyncio.Event()

        async def producer() -> AsyncIterator[ChatEvent]:
            try:
                await asyncio.sleep(10)
                yield {"t": "text", "v": "never"}
            except asyncio.CancelledError:
                stopped.set()
                raise

        frames = [
            frame
            async for frame in sse_stream(
                producer(), heartbeat_seconds=0.02, turn_timeout_seconds=0.1
            )
        ]
        assert _decode(frames[-1]) == {"t": "error", "v": TIMEOUT_MESSAGE}
        assert stopped.is_set()
