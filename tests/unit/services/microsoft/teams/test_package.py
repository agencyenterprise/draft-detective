"""Tests for the Teams app package and the manifest in it.

Two of its fields have already cost a debugging session each, and both fail in ways
that name something else entirely:

- ``validDomains`` without ``token.botframework.com`` makes Teams refuse to open the
  sign-in link, reporting "this action can't be performed since the app does not exist
  or has been uninstalled".
- ``webApplicationInfo`` is deliberately absent. Present, Teams attempts a silent token
  exchange, and unbacked by Azure configuration that fails and falls back to the card --
  looking exactly like the field was never there, only slower.

So the manifest is asserted rather than eyeballed.
"""

import io
import json
import zipfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from lib.api.routers.microsoft import teams
from lib.services.microsoft.teams import package

FRONTEND = "https://dd.example.com"


class TestSignInCanOpenAtAll:
    def test_the_token_service_domain_is_trusted(self) -> None:
        """Teams will not open a link on a domain the manifest has not declared.

        This app has no tabs, so an empty ``validDomains`` looks right -- and it was,
        which is what broke sign-in in every scope.
        """

        document = package.manifest("b", "1.0.0", FRONTEND)

        assert "token.botframework.com" in document["validDomains"]


class TestSSOIsNotDeclared:
    """Sign-in is a deliberate click, so ``webApplicationInfo`` must stay absent.

    It was implemented and removed. Declaring it makes Teams attempt a silent
    ``signin/tokenExchange``, which needs an Application ID URI, an exposed scope and
    the Teams client ids pre-authorised on a registration -- and buys only the removal
    of one click, once per person, since Teams cannot acquire a token in a channel
    either way. Unbacked, the exchange fails and falls back to the card, which is
    indistinguishable from this being absent except slower.
    """

    def test_the_manifest_declares_no_sso(self) -> None:
        document = package.manifest("b", "1.0.0", FRONTEND)

        assert "webApplicationInfo" not in document

    def test_nothing_builds_one(self) -> None:
        """Guards the removal, so it does not come back unnoticed."""

        assert not hasattr(package, "sso_declaration")


class TestTheRestOfTheManifest:
    def test_the_bot_is_offered_in_every_scope_it_supports(self) -> None:
        document = package.manifest("b", "1.0.0", FRONTEND)

        assert set(document["bots"][0]["scopes"]) == {"personal", "team", "groupChat"}

    def test_personal_scope_is_present_because_sign_in_needs_it(self) -> None:
        """Teams cannot acquire a token in a channel, so 1:1 has to be installable."""

        assert (
            "personal" in package.manifest("b", "1.0.0", FRONTEND)["bots"][0]["scopes"]
        )

    def test_the_version_is_what_was_asked_for(self) -> None:
        """Teams refuses an update that does not raise the version."""

        assert package.manifest("b", "9.9.9", FRONTEND)["version"] == "9.9.9"


class TestThePackage:
    def test_it_holds_the_manifest_and_icons_of_the_sizes_teams_requires(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(package.package("bot-id", f"{FRONTEND}/")))

        document = json.loads(archive.read("manifest.json"))
        assert document["id"] == document["bots"][0]["botId"] == "bot-id"
        assert document["version"] == package.app_version()
        assert document["developer"]["websiteUrl"] == FRONTEND
        assert document["developer"]["privacyUrl"] == f"{FRONTEND}/about"
        sizes = {
            name: Image.open(io.BytesIO(archive.read(name))).size
            for name in ("color.png", "outline.png")
        }
        assert sizes == {"color.png": (192, 192), "outline.png": (32, 32)}

    def test_the_colour_icon_is_a_full_square(self) -> None:
        """Teams rounds the corners itself, so pre-rounded ones come out doubled."""

        colour = Image.open(package.ICONS / "color.png").convert("RGBA")

        assert colour.getchannel("A").getextrema() == (255, 255)

    def test_the_outline_is_only_opaque_white_or_transparent(self) -> None:
        """Teams refuses any other pixel with ``InvalidOutlineIconTransparency``."""

        outline = Image.open(package.ICONS / "outline.png").convert("RGBA")

        pixels = set(outline.get_flattened_data())
        assert pixels <= {(255, 255, 255, 255), (0, 0, 0, 0)}


def client() -> TestClient:
    app = FastAPI()
    app.include_router(teams.router, prefix="/api/microsoft")
    return TestClient(app)


class TestTheDownload:
    def test_a_configured_bot_gets_its_package(self) -> None:
        with (
            patch.object(teams.bot, "missing", return_value=None),
            patch.object(teams.config, "TEAMS_BOT_APP_ID", "bot-id"),
            patch.object(teams.config, "FRONTEND_URL", FRONTEND),
        ):
            response = client().get("/api/microsoft/teams/package.zip")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        manifest = zipfile.ZipFile(io.BytesIO(response.content)).read("manifest.json")
        assert json.loads(manifest)["bots"][0]["botId"] == "bot-id"

    def test_it_is_refused_until_the_bot_is_configured(self) -> None:
        """A package for a bot that cannot answer would publish a broken app."""

        with patch.object(teams.bot, "missing", return_value="Set TEAMS_BOT_APP_ID"):
            response = client().get("/api/microsoft/teams/package.zip")

        assert response.status_code == 503
        assert "TEAMS_BOT_APP_ID" in response.text

    def test_it_is_refused_while_the_frontend_is_not_https(self) -> None:
        """Teams refuses a package whose developer links are not HTTPS."""

        with (
            patch.object(teams.bot, "missing", return_value=None),
            patch.object(teams.config, "TEAMS_BOT_APP_ID", "bot-id"),
            patch.object(teams.config, "FRONTEND_URL", "http://localhost:3000"),
        ):
            response = client().get("/api/microsoft/teams/package.zip")

        assert response.status_code == 503
        assert "FRONTEND_URL" in response.text
