"""The admin dashboard endpoint's cache is what keeps repeat loads off the DB.

Each computation is a set of sequential scans over `workflow_runs` holding one
pooled connection, so "several admins refresh at once" must not mean "several
sets of scans". These tests pin the two properties that guarantee it: concurrent
callers share one in-flight computation, and each window is cached separately.
"""

import asyncio
import uuid

import aiotools
import pytest

from lib.api.routers import admin_dashboard


@pytest.fixture(autouse=True)
def clear_cache():
    admin_dashboard._cached_dashboard.cache_clear()
    yield
    admin_dashboard._cached_dashboard.cache_clear()


NOBODY: tuple[uuid.UUID, ...] = ()


class _Recorder:
    """Stands in for the service, counting how often it is actually run."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, tuple[uuid.UUID, ...]]] = []

    async def __call__(self, days: int, ignored_user_ids: tuple[uuid.UUID, ...]) -> str:
        self.calls.append((days, ignored_user_ids))
        await asyncio.sleep(0.05)  # long enough for the other callers to arrive
        return f"payload-{days}-{len(ignored_user_ids)}"


@pytest.mark.asyncio
async def test_concurrent_requests_for_one_window_share_a_single_computation(
    monkeypatch,
):
    recorder = _Recorder()
    monkeypatch.setattr(admin_dashboard, "get_admin_dashboard", recorder)

    results = await asyncio.gather(
        *[admin_dashboard._cached_dashboard(30, NOBODY) for _ in range(25)]
    )

    assert recorder.calls == [(30, NOBODY)]
    assert results == ["payload-30-0"] * 25


@pytest.mark.asyncio
async def test_a_second_load_of_the_same_window_is_served_from_the_cache(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(admin_dashboard, "get_admin_dashboard", recorder)

    first = await admin_dashboard._cached_dashboard(7, NOBODY)
    second = await admin_dashboard._cached_dashboard(7, NOBODY)

    assert recorder.calls == [(7, NOBODY)]
    assert first == second


@pytest.mark.asyncio
async def test_each_window_is_cached_separately(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(admin_dashboard, "get_admin_dashboard", recorder)

    for days in (7, 30, 90, 365):
        await admin_dashboard._cached_dashboard(days, NOBODY)

    assert recorder.calls == [(days, NOBODY) for days in (7, 30, 90, 365)]


@pytest.mark.asyncio
async def test_each_ignore_list_is_cached_separately(monkeypatch):
    """Leaving the eval account out is a different set of figures."""
    recorder = _Recorder()
    monkeypatch.setattr(admin_dashboard, "get_admin_dashboard", recorder)
    eval_user = (uuid.uuid4(),)

    await admin_dashboard._cached_dashboard(30, NOBODY)
    await admin_dashboard._cached_dashboard(30, eval_user)
    await admin_dashboard._cached_dashboard(30, eval_user)

    assert recorder.calls == [(30, NOBODY), (30, eval_user)]


def test_cache_is_bounded():
    """A caller churning `days` values must not grow the cache without bound."""
    assert admin_dashboard._cached_dashboard.cache_parameters()["maxsize"] == (
        admin_dashboard._CACHE_MAXSIZE
    )


@pytest.mark.asyncio
async def test_entries_are_recomputed_once_the_ttl_passes():
    """The property `CACHE_TTL_SECONDS` relies on, at a testable timescale.

    `cache_parameters()` does not report the TTL, so the expiry semantics the
    endpoint depends on are pinned here against the same decorator instead.
    """
    calls: list[int] = []

    @aiotools.lru_cache(maxsize=admin_dashboard._CACHE_MAXSIZE, expire_after=0.1)
    async def cached(days: int, ignored_user_ids: tuple[uuid.UUID, ...]) -> int:
        calls.append(days)
        return days

    await cached(30, NOBODY)
    await cached(30, NOBODY)
    assert calls == [30]

    await asyncio.sleep(0.15)
    await cached(30, NOBODY)

    assert calls == [30, 30]
