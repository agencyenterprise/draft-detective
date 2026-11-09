"""A chat turn run apart from the request that started it (``detached_turn``).

The claim is kept in memory here; ``tests/integration/test_chat_turn_claims.py``
covers the database's version of it, stale claims included.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from lib.services.chat import detached_turn
from lib.services.chat.detached_turn import (
    TIMEOUT_MESSAGE,
    TurnAlreadyRunning,
    start_turn,
)
from lib.services.chat.events import ChatEvent, detached_event
from lib.services.chat.sse import sse_stream

THREAD = uuid.uuid4()


class MemoryClaims:
    """One claim per thread; ``stop`` is what a cancel request or a lost claim does."""

    def __init__(self) -> None:
        self.held: dict[uuid.UUID, datetime] = {}
        self.stop = False
        self.released = asyncio.Event()

    async def claim(self, thread_id: uuid.UUID) -> datetime | None:
        if thread_id in self.held:
            return None
        self.held[thread_id] = datetime.now(UTC)
        return self.held[thread_id]

    async def keep(self, thread_id: uuid.UUID, token: datetime) -> bool:
        return not self.stop and self.held.get(thread_id) == token

    async def release(self, thread_id: uuid.UUID, token: datetime) -> None:
        if self.held.get(thread_id) == token:
            del self.held[thread_id]
        self.released.set()


class Agent:
    """A turn's events, saying how far it got and whether it was cancelled."""

    def __init__(self, *events: ChatEvent, delay: float = 0.0) -> None:
        self.events, self.delay = events, delay
        self.sent: list[ChatEvent] = []
        self.started = False
        self.cancelled = False

    async def run(self) -> AsyncIterator[ChatEvent]:
        self.started = True
        try:
            for event in self.events:
                await asyncio.sleep(self.delay)
                self.sent.append(event)
                yield event
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def text(v: str) -> ChatEvent:
    return {"t": "text", "v": v}


@pytest.fixture
def claims() -> MemoryClaims:
    return MemoryClaims()


@pytest.mark.asyncio
async def test_the_listener_gets_every_event_and_the_claim_is_released(
    claims: MemoryClaims,
) -> None:
    agent = Agent(text("a"), text("b"))
    turn = await start_turn(THREAD, agent.run(), claims=claims)

    assert [event async for event in turn.events()] == [text("a"), text("b")]
    await asyncio.wait_for(claims.released.wait(), timeout=1)
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_a_listener_that_leaves_does_not_stop_the_turn(
    claims: MemoryClaims,
) -> None:
    agent = Agent(text("a"), text("b"), text("c"), delay=0.02)
    turn = await start_turn(THREAD, agent.run(), claims=claims)

    events = turn.events()
    assert await anext(events) == text("a")
    await events.aclose()  # type: ignore[attr-defined]  # an async generator

    assert turn.task is not None
    await asyncio.wait_for(turn.task, timeout=1)
    assert agent.sent == [text("a"), text("b"), text("c")]
    assert not agent.cancelled
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_a_second_turn_on_the_thread_is_refused_and_never_started(
    claims: MemoryClaims,
) -> None:
    first = Agent(text("a"), delay=0.05)
    turn = await start_turn(THREAD, first.run(), claims=claims)
    second = Agent(text("b"))

    with pytest.raises(TurnAlreadyRunning):
        await start_turn(THREAD, second.run(), claims=claims)

    assert not second.started
    assert turn.task is not None
    await turn.task
    # Once the first lets go, the thread takes a turn again.
    again = await start_turn(THREAD, Agent().run(), claims=claims)
    assert [event async for event in again.events()] == []


@pytest.mark.asyncio
async def test_a_cancel_request_stops_the_turn_and_lets_go(
    claims: MemoryClaims,
) -> None:
    agent = Agent(text("a"), text("never"), delay=0.2)
    turn = await start_turn(THREAD, agent.run(), claims=claims, keep_seconds=0.02)

    claims.stop = True
    assert [event async for event in turn.events()] == []
    assert agent.cancelled
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_a_turn_whose_stale_claim_was_taken_stops_without_freeing_the_new_one(
    claims: MemoryClaims,
) -> None:
    agent = Agent(text("never"), delay=0.2)
    turn = await start_turn(THREAD, agent.run(), claims=claims, keep_seconds=0.02)
    # Another worker took the claim after this one went stale.
    claims.held[THREAD] = datetime.now(UTC)
    taken = claims.held[THREAD]

    assert turn.task is not None
    await asyncio.wait_for(turn.task, timeout=1)
    assert agent.cancelled
    assert claims.held[THREAD] == taken


@pytest.mark.asyncio
@pytest.mark.parametrize("stamp", ["fails", "hangs"])
async def test_a_turn_that_cannot_stamp_its_claim_stops_before_it_goes_stale(
    claims: MemoryClaims, stamp: str
) -> None:
    async def broken_keep(thread_id: uuid.UUID, token: datetime) -> bool:
        if stamp == "hangs":
            await asyncio.sleep(10)
        raise ConnectionError("database unavailable")

    claims.keep = broken_keep  # type: ignore[method-assign]
    agent = Agent(text("never"), delay=10)
    turn = await start_turn(
        THREAD, agent.run(), claims=claims, keep_seconds=0.02, lease_seconds=0.1
    )

    assert turn.task is not None
    await asyncio.wait_for(turn.task, timeout=1)
    assert agent.cancelled
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_a_listener_that_never_reads_holds_a_bounded_buffer(
    claims: MemoryClaims, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(detached_turn, "MAX_BUFFERED_EVENTS", 3)
    agent = Agent(*(text(str(i)) for i in range(10)))
    turn = await start_turn(THREAD, agent.run(), claims=claims)

    # The client left before reading anything; the turn runs to the end regardless.
    assert turn.task is not None
    await asyncio.wait_for(turn.task, timeout=1)
    assert len(agent.sent) == 10
    # A listener that does turn up is handed over to the stored history.
    assert [event async for event in turn.events()] == [{"t": "detached"}]


@pytest.mark.asyncio
async def test_a_failing_turn_ends_with_an_error_event(claims: MemoryClaims) -> None:
    async def failing() -> AsyncIterator[ChatEvent]:
        yield text("partial")
        raise RuntimeError("model unavailable")

    turn = await start_turn(THREAD, failing(), claims=claims)

    assert [event async for event in turn.events()] == [
        text("partial"),
        {"t": "error", "v": "model unavailable"},
    ]
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_a_hung_turn_is_stopped_at_the_turn_limit(claims: MemoryClaims) -> None:
    agent = Agent(text("never"), delay=10)
    turn = await start_turn(THREAD, agent.run(), claims=claims, max_turn_seconds=0.05)

    assert [event async for event in turn.events()] == [
        {"t": "error", "v": TIMEOUT_MESSAGE}
    ]
    assert agent.cancelled
    assert THREAD not in claims.held


@pytest.mark.asyncio
async def test_the_stream_cap_ends_the_stream_with_detached_and_the_turn_runs_on(
    claims: MemoryClaims,
) -> None:
    agent = Agent(text("a"), text("b"), delay=0.1)
    turn = await start_turn(THREAD, agent.run(), claims=claims)

    frames = [
        frame
        async for frame in sse_stream(
            turn.events(),
            heartbeat_seconds=0.02,
            turn_timeout_seconds=0.15,
            timeout_event=detached_event(),
        )
    ]
    data = [json.loads(f[len("data: ") :]) for f in frames if f.startswith("data:")]
    assert data == [text("a"), {"t": "detached"}]

    assert turn.task is not None
    await asyncio.wait_for(turn.task, timeout=1)
    assert agent.sent == [text("a"), text("b")]
    assert not agent.cancelled
