"""Run a turn on a chat thread in a task of its own, apart from the request that asks.

A turn that runs inside its request ends with it: a closed tab, a dropped connection
or the proxy's 15-minute cap would cancel the agent mid-turn. Here the request only
starts the turn and listens to it. Once started, a turn ends in one of three ways:

- its events run out, or it fails (the failure becomes an ``error`` event);
- someone asks it to stop, from any worker (``turn_claims.request_cancel``), and it
  notices on its next stamp, within ``KEEP_SECONDS``;
- it can't stamp its claim for ``LEASE_SECONDS`` (the database is down, or a stamp
  hangs), and so stops before the claim could go stale and be taken by another;
- it runs past ``MAX_TURN_SECONDS``.

The thread is claimed while the turn runs, so a second turn is refused
(``TurnAlreadyRunning``). The runner knows nothing about which agent it runs: it takes
the turn's events, as any agent on ``chat_threads`` produces them.

Usage::

    turn = await start_turn(thread_id, run_chat_turn(...))
    async for event in turn.events():  # stop listening any time; the turn goes on
        ...
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Coroutine
from contextlib import suppress
from datetime import datetime
from typing import Any, Protocol

from lib.models.chat_thread import STALE_TURN
from lib.services.chat import turn_claims
from lib.services.chat.events import ChatEvent, detached_event, error_event

logger = logging.getLogger(__name__)

# How often the turn stamps its claim, and so how soon it notices a cancel request.
KEEP_SECONDS = 3.0
# How long a turn runs on without a stamp. Half of ``STALE_TURN``: the turn stops
# well before another worker could take its claim, clock skew between workers and
# the database included.
LEASE_SECONDS = STALE_TURN.total_seconds() / 2
# A last resort for a turn that hangs. Long research turns run for 10+ minutes.
MAX_TURN_SECONDS = 60 * 60.0
# Events held for a listener that hasn't read them. A listener this far behind
# (or one whose client left before the response body started) is gone.
MAX_BUFFERED_EVENTS = 10_000
TIMEOUT_MESSAGE = "This turn ran past the time limit and was stopped."


class TurnAlreadyRunning(Exception):
    """Another turn holds the thread."""


class TurnClaims(Protocol):
    """Where the claim on a thread is kept; ``turn_claims`` in production."""

    async def claim(self, thread_id: uuid.UUID) -> datetime | None: ...

    async def keep(self, thread_id: uuid.UUID, token: datetime) -> bool: ...

    async def release(self, thread_id: uuid.UUID, token: datetime) -> None: ...


class _DatabaseClaims:
    async def claim(self, thread_id: uuid.UUID) -> datetime | None:
        return await turn_claims.claim(thread_id)

    async def keep(self, thread_id: uuid.UUID, token: datetime) -> bool:
        return await turn_claims.keep(thread_id, token)

    async def release(self, thread_id: uuid.UUID, token: datetime) -> None:
        await turn_claims.release(thread_id, token)


DATABASE_CLAIMS: TurnClaims = _DatabaseClaims()

# The event loop keeps only weak references to tasks: a turn nobody listens to
# anymore would otherwise be collected mid-run.
_RUNNING: set[asyncio.Task[None]] = set()


class DetachedTurn:
    """A running turn, and one listener's view of its events.

    Events are buffered for the listener until it stops listening, or falls
    ``MAX_BUFFERED_EVENTS`` behind; after that they are dropped, and the turn runs
    on with only the checkpointer recording it.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ChatEvent | None] = asyncio.Queue(
            MAX_BUFFERED_EVENTS
        )
        self._listening = True
        self.task: asyncio.Task[None] | None = None

    async def events(self) -> AsyncIterator[ChatEvent]:
        """The turn's events until it ends. Closing this only stops the listening."""

        try:
            while (event := await self._queue.get()) is not None:
                yield event
        finally:
            self._listening = False

    def _emit(self, event: ChatEvent | None) -> None:
        if not self._listening:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # Hand a listener that is still there over to the stored history.
            self._listening = False
            while not self._queue.empty():
                self._queue.get_nowait()
            self._queue.put_nowait(detached_event())
            self._queue.put_nowait(None)


async def start_turn(
    thread_id: uuid.UUID,
    events: AsyncIterator[ChatEvent],
    *,
    claims: TurnClaims = DATABASE_CLAIMS,
    keep_seconds: float = KEEP_SECONDS,
    lease_seconds: float = LEASE_SECONDS,
    max_turn_seconds: float = MAX_TURN_SECONDS,
) -> DetachedTurn:
    """Claim the thread and start the turn in the background.

    Raises ``TurnAlreadyRunning`` when another turn holds the thread; ``events`` is
    then never started.
    """

    token = await claims.claim(thread_id)
    if token is None:
        raise TurnAlreadyRunning(str(thread_id))
    turn = DetachedTurn()
    claim = _Claim(claims, thread_id, token)
    run = _run(turn, events, claim, keep_seconds, lease_seconds)
    turn.task = asyncio.create_task(_capped(turn, run, max_turn_seconds))
    _RUNNING.add(turn.task)
    turn.task.add_done_callback(_RUNNING.discard)
    return turn


class _Claim:
    def __init__(
        self, claims: TurnClaims, thread_id: uuid.UUID, token: datetime
    ) -> None:
        self.claims, self.thread_id, self.token = claims, thread_id, token

    async def keep(self) -> bool:
        return await self.claims.keep(self.thread_id, self.token)

    async def release(self) -> None:
        await self.claims.release(self.thread_id, self.token)


async def _capped(
    turn: DetachedTurn, run: Coroutine[Any, Any, None], limit: float
) -> None:
    try:
        async with asyncio.timeout(limit):
            await run
    except TimeoutError:
        turn._emit(error_event(TIMEOUT_MESSAGE))
    finally:
        turn._emit(None)


async def _run(
    turn: DetachedTurn,
    events: AsyncIterator[ChatEvent],
    claim: _Claim,
    keep_seconds: float,
    lease_seconds: float,
) -> None:
    """Drain the events until they end or the turn should stop, then let go."""

    producer = asyncio.create_task(_drain(turn, events))
    watcher = asyncio.create_task(_watch(claim, keep_seconds, lease_seconds))
    try:
        await asyncio.wait({producer, watcher}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (producer, watcher):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        # Shielded: a turn cancelled at shutdown must still try to let go.
        await asyncio.shield(_release(claim))


async def _drain(turn: DetachedTurn, events: AsyncIterator[ChatEvent]) -> None:
    try:
        async for event in events:
            turn._emit(event)
    except Exception as error:  # noqa: BLE001 - reported to the listener as an event
        logger.exception("chat turn failed")
        turn._emit(error_event(str(error) or "The turn failed."))


async def _watch(claim: _Claim, keep_seconds: float, lease_seconds: float) -> None:
    """Return once the turn should stop: a cancel request, its claim lost, or no
    stamp for ``lease_seconds``."""

    loop = asyncio.get_running_loop()
    kept_at = loop.time()
    while True:
        await asyncio.sleep(keep_seconds)
        left = lease_seconds - (loop.time() - kept_at)
        if left <= 0:
            logger.error("chat turn stopped: its claim went unstamped too long")
            return
        try:
            async with asyncio.timeout(left):
                if not await claim.keep():
                    return
            kept_at = loop.time()
        except TimeoutError:
            logger.error("chat turn stopped: stamping its claim hung too long")
            return
        except Exception:  # noqa: BLE001 - a database blip must not stop the turn
            logger.exception("could not stamp the chat turn's claim")


async def _release(claim: _Claim) -> None:
    try:
        await claim.release()
    except Exception:  # noqa: BLE001 - the claim then goes stale on its own
        logger.exception("could not release the chat turn's claim")
