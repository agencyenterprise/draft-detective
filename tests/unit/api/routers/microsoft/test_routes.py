"""Tests for the paths and sign-in of every Microsoft 365 route.

These paths are registered outside this repo: the Bot Connector posts to the Teams
messaging endpoint configured in Azure, and the add-in calls the Word routes. Each
endpoint's own tests call it directly, so the prefixes and the dependency that scopes a
call to the signed-in account are pinned here, on the router the application mounts.
"""

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from lib.api.addin_auth import get_addin_identity
from lib.api.auth import get_current_user, get_current_user_optional
from lib.api.routers.microsoft import routes


def mounted() -> dict[str, APIRoute]:
    """Just these routes, not the whole application (see ``test_teams``)."""

    app = FastAPI()
    app.include_router(routes.router)
    return {
        f"{method} {route.path}": route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def depends_on(dependant: Dependant, dependency: object) -> bool:
    return any(
        sub.call is dependency or depends_on(sub, dependency)
        for sub in dependant.dependencies
    )


def test_the_routes_are_where_their_callers_look() -> None:
    assert set(mounted()) == {
        "POST /api/microsoft/teams/messages",
        "GET /api/microsoft/teams/package.zip",
        "GET /api/microsoft/word/features",
        "GET /api/microsoft/word/handoffs",
        "POST /api/microsoft/word/handoffs/{handoff_id}/started",
        "POST /api/microsoft/word/handoffs/{handoff_id}/applied",
        "POST /api/microsoft/word/handoffs/{handoff_id}/dismissed",
        "GET /api/microsoft/word/chat/thread",
        "POST /api/microsoft/word/chat/thread/stream",
        "POST /api/microsoft/word/chat/thread/resume",
        "POST /api/microsoft/word/chat/thread/clear",
        "GET /api/microsoft/word/chat/suggestions/{suggestion_id}",
        "GET /api/microsoft/word/chat/checks",
    }


def test_every_word_route_is_scoped_to_the_add_ins_account() -> None:
    """A route added without the add-in's sign-in would answer anyone."""

    word = {key: route for key, route in mounted().items() if "/word/" in key}

    unscoped = [
        key
        for key, route in word.items()
        if not depends_on(route.dependant, get_addin_identity)
    ]
    assert word and unscoped == []


def test_the_bot_endpoint_is_not_behind_a_draft_detective_sign_in() -> None:
    """The Bot Connector presents its own token, which the bot validates."""

    bot = mounted()["POST /api/microsoft/teams/messages"]

    for sign_in in (get_current_user, get_current_user_optional, get_addin_identity):
        assert not depends_on(bot.dependant, sign_in)
