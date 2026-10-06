"""Tests for the sign-in storage the Agents SDK writes through.

The bug this exists for is invisible on one machine. A sign-in spans two requests --
the message that posts the Sign in card, then the ``signin/*`` invoke that completes
it -- and production runs Uvicorn with ``--workers 4``. With the SDK's ``MemoryStorage``
the second request usually lands on a worker that has never heard of the flow, so the
parked question is lost and first-time sign-in fails perhaps three times in four. A
single-process dev server never shows it, and no test that shares a process would
either, which is why the property asserted here is *where* the state lives rather than
that a round trip works.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents.hosting.core.storage import StoreItem

from lib.services.microsoft.teams import storage as signin_storage


class Item(StoreItem):
    """The shape the SDK stores: something that round-trips through JSON."""

    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def store_item_to_json(self) -> dict[str, Any]:
        return self.value

    @staticmethod
    def from_json_to_store_item(json_data: Any) -> "Item":
        return Item(json_data)


def session_returning(row: Any, swept: int = 0) -> Any:
    """An async session whose queries yield ``row``, and report ``swept`` deletions."""

    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.rowcount = swept

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def statements(session: Any) -> list[str]:
    """Every statement the session was asked to run, lowercased."""

    return [str(call[0][0]).lower() for call in session.execute.await_args_list]


class TestWhereSignInStateLives:
    def test_it_is_not_the_sdk_memory_storage(self) -> None:
        """The whole point. In-process state cannot span four workers."""

        from microsoft_agents.hosting.core import MemoryStorage

        assert not isinstance(signin_storage.sign_in_storage(), MemoryStorage)

    def test_the_bot_actually_builds_with_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserted on the built object, not on source text: what matters is the
        storage the SDK ends up holding, since that is what spans the two requests."""

        from lib.config.env import config
        from lib.services.microsoft.teams import bot

        monkeypatch.setattr(config, "TEAMS_BOT_APP_ID", "11111111-2222-3333-4444-555555555555")
        monkeypatch.setattr(config, "TEAMS_BOT_APP_PASSWORD", "a-secret")
        monkeypatch.setattr(config, "TEAMS_USER_AUTH_CONNECTION", "graph-user")
        monkeypatch.setattr(bot, "bot", bot._Bot())
        bot.bot._build()

        held = bot.bot.application._storage
        assert isinstance(held, signin_storage.PostgresSignInStorage), (
            f"the SDK is holding {type(held).__name__}, which cannot span workers"
        )


class TestReadingAndWriting:
    @pytest.mark.asyncio
    async def test_a_missing_key_reads_as_nothing(self) -> None:
        """A flow the SDK has not started yet, or one already completed."""

        with patch.object(
            signin_storage, "get_async_db_session", lambda: session_returning(None)
        ):
            key, item = await signin_storage.PostgresSignInStorage()._read_item(
                "conv/user", target_cls=Item
            )

        assert (key, item) == (None, None)

    @pytest.mark.asyncio
    async def test_a_stored_value_comes_back_through_the_target_class(self) -> None:
        row = MagicMock(value={"parked": "the question"})
        with patch.object(
            signin_storage, "get_async_db_session", lambda: session_returning(row)
        ):
            key, item = await signin_storage.PostgresSignInStorage()._read_item(
                "conv/user", target_cls=Item
            )

        assert key == "conv/user"
        assert item is not None and item.value == {"parked": "the question"}

    @pytest.mark.asyncio
    async def test_writing_upserts_so_a_retried_turn_does_not_collide(self) -> None:
        """The Connector retries, and a retry must rewrite rather than fail."""

        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "the question"})
            )

        session.commit.assert_awaited_once()
        assert any(
            "on conflict" in statement for statement in statements(session)
        ), "a retried turn would otherwise raise"

    @pytest.mark.asyncio
    async def test_writing_stamps_a_time_for_sweeping_abandoned_flows(self) -> None:
        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "q"})
            )

        values = session.execute.await_args_list[0][0][0].compile().params
        assert isinstance(values["updated_at"], datetime)

    @pytest.mark.asyncio
    async def test_deleting_a_completed_flow_commits(self) -> None:
        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._delete_item("conv/user")

        assert "delete" in statements(session)[0]
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_bulk_operations_come_from_the_sdk_base(self) -> None:
        """``AsyncStorageBase`` builds read/write/delete from the single-item hooks."""

        store = signin_storage.PostgresSignInStorage()
        row = MagicMock(value={"a": 1})
        with patch.object(
            signin_storage, "get_async_db_session", lambda: session_returning(row)
        ):
            found = await store.read(["one", "two"], target_cls=Item)

        assert set(found) == {"one", "two"}


class TestSweepingAbandonedSignIns:
    """A sign-in nobody finishes never deletes its own row.

    The SDK removes an entry when a flow completes or fails, so what lingers is the case
    where somebody saw the Sign in card and closed it. Those rows hold the parked
    message -- its text and its sender -- so leaving them is retaining confidential
    content indefinitely in a table documented as short lived.
    """

    @pytest.mark.asyncio
    async def test_a_write_also_deletes_stale_rows(self) -> None:
        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "q"})
            )

        ran = statements(session)
        assert any("on conflict" in statement for statement in ran), "the write itself"
        assert any(
            statement.startswith("delete") for statement in ran
        ), "nothing sweeps, so an abandoned sign-in is kept forever"

    @pytest.mark.asyncio
    async def test_the_sweep_shares_the_write_transaction(self) -> None:
        """One commit: a sweep that failed alone would look like a failed write."""

        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "q"})
            )

        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_window_is_generous_next_to_a_flow(self) -> None:
        """The SDK's flow lasts about a minute, so an hour cannot cut one short."""

        assert signin_storage.ABANDONED_AFTER >= timedelta(minutes=30)
        assert signin_storage.ABANDONED_AFTER <= timedelta(days=1)

    @pytest.mark.asyncio
    async def test_the_sweep_filters_on_the_indexed_column(self) -> None:
        """A sweep on an unindexed column would scan the table on every write."""

        session = session_returning(None)
        with patch.object(signin_storage, "get_async_db_session", lambda: session):
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "q"})
            )

        sweep = next(s for s in statements(session) if s.startswith("delete"))
        assert "updated_at" in sweep

    @pytest.mark.asyncio
    async def test_a_sweep_that_removed_rows_says_so(self) -> None:
        """Silent deletion of message-bearing rows is not something to do unlogged."""

        session = session_returning(None, swept=3)
        with patch.object(
            signin_storage, "get_async_db_session", lambda: session
        ), patch.object(signin_storage.logger, "info") as logged:
            await signin_storage.PostgresSignInStorage()._write_item(
                "conv/user", Item({"parked": "q"})
            )

        assert logged.called
        assert logged.call_args[0][1] == 3
