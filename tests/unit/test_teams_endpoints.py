"""Tests for the Teams messaging endpoint.

The endpoint only maps the outcome of a turn to what the Bot Connector expects. The
authentication boundary is covered in ``test_teams_bot.py``, where the token validation
lives, and what the bot does with an activity in ``test_teams_conversation.py``.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from lib.api.routers.microsoft import teams


class TestAnsweringAnInvoke:
    """The sign-in card's invoke reply is protocol, not a formality.

    Teams reads the body to decide whether to open the sign-in window or replace the
    card, so the endpoint passes the turn's reply through rather than an empty 200.
    """

    LOGIN_REQUEST = {
        "statusCode": 401,
        "type": "application/vnd.microsoft.activity.loginRequest",
        "value": {"connectionName": "graph-user", "buttons": []},
    }

    def response_for(self, status: int, body: Any) -> Any:
        from microsoft_agents.activity.invoke_response import InvokeResponse

        return InvokeResponse(status=status, body=body)

    def test_the_body_reaches_teams_unchanged(self) -> None:
        response = teams._invoke_response(self.response_for(200, self.LOGIN_REQUEST))

        assert response.status_code == 200
        assert response.media_type == "application/json"
        assert json.loads(response.body) == self.LOGIN_REQUEST

    def test_no_body_keeps_its_status(self) -> None:
        """An invoke no route handled comes back 501 with nothing to send."""

        response = teams._invoke_response(self.response_for(501, None))

        assert response.status_code == 501
        assert not response.body

    def client(self) -> Any:
        """Just this router, not the whole application.

        Importing ``lib.api.main`` here builds every route and reads module-level
        config, which made this test depend on which other test had run first.
        """

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(teams.router, prefix="/api/microsoft")
        return TestClient(app, raise_server_exceptions=False)

    def test_an_ordinary_message_still_gets_an_empty_200(self) -> None:
        """The Connector treats a body on a normal activity as a payload."""

        with patch.object(teams.bot, "handle", AsyncMock(return_value=None)):
            result = self.client().post(
                "/api/microsoft/teams/messages",
                json={"type": "message", "text": "hi", "conversation": {"id": "19:x"}},
                headers={"Authorization": "Bearer ok"},
            )

        assert result.status_code == 200
        assert result.content == b""

    def test_an_invoke_reply_reaches_the_channel_over_http(self) -> None:
        """End to end through the route, since the reply is the whole point."""

        with patch.object(
            teams.bot,
            "handle",
            AsyncMock(return_value=self.response_for(200, self.LOGIN_REQUEST)),
        ):
            result = self.client().post(
                "/api/microsoft/teams/messages",
                json={"type": "invoke", "name": "adaptiveCard/action"},
                headers={"Authorization": "Bearer ok"},
            )

        assert result.status_code == 200
        assert result.json() == self.LOGIN_REQUEST
