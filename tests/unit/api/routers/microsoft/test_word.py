"""Tests for the add-in's side of Teams handoffs.

The routes are thin, so what is pinned is the contract around them: every call is
scoped to the signed-in Microsoft account, a handoff that is not theirs (or no longer
open) is a 404, and results that do not describe the handoff's own items are refused
rather than posted. ``TestTheRequestTheAddInSends`` goes through HTTP, for what FastAPI
refuses before a route runs.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lib.api.addin_auth import AddinIdentity, get_addin_identity
from lib.api.routers.microsoft import word
from lib.api.routers.microsoft.word import HandoffReport
from lib.services.microsoft.word.handoffs import Account, InvalidResults, ItemResult

ANA = Account(oid="oid-ana", tid="tid-contoso")
RESULTS = [
    ItemResult(index=0, applied=True),
    ItemResult(index=1, applied=False, reason="not_found"),
]


def caller() -> AddinIdentity:
    return AddinIdentity(oid=ANA.oid, tid=ANA.tid, email="ana@contoso.com")


class TestListing:
    @pytest.mark.asyncio
    async def test_it_looks_up_by_the_signed_in_account(self) -> None:
        with patch.object(
            word.handoffs, "pending_for", AsyncMock(return_value=[])
        ) as pending:
            result = await word.list_pending(url="https://x/doc.docx", caller=caller())

        pending.assert_awaited_once_with(ANA)
        assert result.here == [] and result.elsewhere == []


class TestStarting:
    @pytest.mark.asyncio
    async def test_a_pending_handoff_is_claimed_for_the_caller(self) -> None:
        handoff_id = uuid.uuid4()
        with patch.object(
            word.handoffs, "start", AsyncMock(return_value=True)
        ) as start:
            await word.start(handoff_id, caller=caller())

        start.assert_awaited_once_with(handoff_id, ANA)

    @pytest.mark.asyncio
    async def test_one_already_started_or_not_theirs_is_a_404(self) -> None:
        with patch.object(word.handoffs, "start", AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as raised:
                await word.start(uuid.uuid4(), caller=caller())

        assert raised.value.status_code == 404


class TestReporting:
    @pytest.mark.asyncio
    async def test_results_are_reported_for_the_caller(self) -> None:
        handoff_id = uuid.uuid4()
        with patch.object(
            word.handoffs, "report_applied", AsyncMock(return_value=True)
        ) as report:
            await word.report_applied(
                handoff_id, HandoffReport(results=RESULTS), caller=caller()
            )

        report.assert_awaited_once_with(handoff_id, ANA, RESULTS)

    @pytest.mark.asyncio
    async def test_not_theirs_is_a_404(self) -> None:
        with patch.object(
            word.handoffs, "report_applied", AsyncMock(return_value=False)
        ):
            with pytest.raises(HTTPException) as raised:
                await word.report_applied(
                    uuid.uuid4(), HandoffReport(results=RESULTS), caller=caller()
                )

        assert raised.value.status_code == 404

    @pytest.mark.asyncio
    async def test_results_for_items_it_does_not_have_are_refused(self) -> None:
        with patch.object(
            word.handoffs,
            "report_applied",
            AsyncMock(side_effect=InvalidResults("no item 9")),
        ):
            with pytest.raises(HTTPException) as raised:
                await word.report_applied(
                    uuid.uuid4(), HandoffReport(results=RESULTS), caller=caller()
                )

        assert raised.value.status_code == 422

    def test_a_report_is_capped(self) -> None:
        with pytest.raises(ValueError):
            HandoffReport(
                results=[ItemResult(index=i, applied=True) for i in range(501)]
            )


class TestDismissing:
    @pytest.mark.asyncio
    async def test_dismissing_someone_elses_is_a_404(self) -> None:
        with patch.object(word.handoffs, "finish", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as raised:
                await word.dismiss(uuid.uuid4(), caller=caller())

        assert raised.value.status_code == 404

    @pytest.mark.asyncio
    async def test_dismissing_closes_it_for_the_caller(self) -> None:
        handoff_id = uuid.uuid4()
        with patch.object(
            word.handoffs, "finish", AsyncMock(return_value=object())
        ) as finish:
            await word.dismiss(handoff_id, caller=caller())

        finish.assert_awaited_once_with(handoff_id, ANA, "dismissed")


class TestTheRequestTheAddInSends:
    """Results arrive from the client and end up worded into Teams, so their shape counts."""

    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(word.router)
        app.dependency_overrides[get_addin_identity] = caller
        return TestClient(app, raise_server_exceptions=False)

    def report(
        self, handoff_id: str, results: list[dict[str, object]]
    ) -> tuple[int, AsyncMock]:
        with patch.object(
            word.handoffs, "report_applied", AsyncMock(return_value=True)
        ) as report:
            response = self.client().post(
                f"/word/handoffs/{handoff_id}/applied", json={"results": results}
            )
        return response.status_code, report

    def test_a_well_formed_report_reaches_the_handoff(self) -> None:
        handoff_id = uuid.uuid4()
        status, reported = self.report(
            str(handoff_id),
            [{"index": 0, "applied": True}, {"index": 1, "applied": False}],
        )

        assert status == 204
        reported.assert_awaited_once_with(
            handoff_id,
            ANA,
            [ItemResult(index=0, applied=True), ItemResult(index=1, applied=False)],
        )

    @pytest.mark.parametrize(
        "result",
        [
            {"index": -1, "applied": True},
            {"index": 0, "applied": False, "reason": "it was a bad edit"},
            {"applied": True},
        ],
        ids=["negative index", "reason not in the set", "no index"],
    )
    def test_a_result_it_cannot_word_is_refused(
        self, result: dict[str, object]
    ) -> None:
        # A reason outside the set would otherwise put the client's words into Teams.
        status, reported = self.report(str(uuid.uuid4()), [result])

        assert status == 422
        reported.assert_not_awaited()

    def test_a_handoff_id_that_is_not_a_uuid_is_refused(self) -> None:
        status, reported = self.report("not-a-uuid", [])

        assert status == 422
        reported.assert_not_awaited()

    def test_listing_needs_the_document_url(self) -> None:
        with patch.object(
            word.handoffs, "pending_for", AsyncMock(return_value=[])
        ) as pending:
            response = self.client().get("/word/handoffs")

        assert response.status_code == 422
        pending.assert_not_awaited()


class TestFeatures:
    """The pane offers the changes from Teams only where the Teams bot runs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("runs", [True, False])
    async def test_it_says_whether_the_teams_bot_runs(self, runs: bool) -> None:
        with patch.object(word.bot, "configured", return_value=runs):
            found = await word.features(caller())

        assert found.teams is runs

    @pytest.mark.parametrize(
        ("app_id", "password", "connection", "runs"),
        [
            ("app", "secret", "graph-user", True),
            (None, "secret", "graph-user", False),
            ("app", None, "graph-user", False),
            ("app", "secret", None, False),
        ],
    )
    def test_the_bot_runs_only_with_every_setting_it_needs(
        self,
        app_id: str | None,
        password: str | None,
        connection: str | None,
        runs: bool,
    ) -> None:
        with (
            patch.object(word.bot.config, "TEAMS_BOT_APP_ID", app_id),
            patch.object(word.bot.config, "TEAMS_BOT_APP_PASSWORD", password),
            patch.object(word.bot.config, "TEAMS_USER_AUTH_CONNECTION", connection),
        ):
            assert word.bot.configured() is runs
