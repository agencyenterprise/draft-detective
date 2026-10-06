"""Tests for reading SharePoint documents through Graph, as the person who asked."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lib.services.microsoft.graph import client
from lib.services.microsoft.graph.client import redacted


class TestResolvingASharingLink:
    """What the Teams path actually receives: "Copy link" in Word produces
    ``/:w:/s/Site/EWabc...``, where the site is an opaque identifier."""

    SHARING_LINK = "https://contoso.sharepoint.com/:w:/s/Reviews/EWabc123?e=xyz"

    def graph(self, web_url: str) -> Any:
        """A Graph client whose ``/shares`` lookup returns one item."""

        response = MagicMock(status_code=200)
        response.json.return_value = {"name": "a.docx", "webUrl": web_url}

        transport = MagicMock()
        transport.get = AsyncMock(return_value=response)
        transport.__aenter__ = AsyncMock(return_value=transport)
        transport.__aexit__ = AsyncMock(return_value=False)
        return transport

    @pytest.mark.asyncio
    async def test_an_opaque_link_resolves(self) -> None:
        graph = self.graph(
            "https://contoso.sharepoint.com/sites/Reviews/Drafts/a.docx"
        )
        with patch("httpx.AsyncClient", return_value=graph):
            item = await client.resolve(self.SHARING_LINK, token="t")

        assert item["name"] == "a.docx"


class TestWhoseIdentityReads:
    """Graph is what enforces a user's own permissions, so it must get their token.

    ``resolve`` and ``download`` take one rather than defaulting it, so a call site
    cannot lose the user's identity by omission.
    """

    def test_neither_call_can_be_made_without_saying_whose_it_is(self) -> None:
        """A keyword-only, non-defaulted token is the whole guard. Pin it."""

        import inspect

        for function in (client.resolve, client.download):
            token = inspect.signature(function).parameters["token"]
            assert token.kind is inspect.Parameter.KEYWORD_ONLY, function.__name__
            assert token.default is inspect.Parameter.empty, (
                f"{function.__name__} must not default whose identity it reads with"
            )

    @pytest.mark.asyncio
    async def test_the_given_token_is_what_graph_is_called_with(self) -> None:
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "name": "a.docx",
            "webUrl": "https://contoso.sharepoint.com/sites/Reviews/a.docx",
        }
        transport = MagicMock()
        transport.get = AsyncMock(return_value=response)
        transport.__aenter__ = AsyncMock(return_value=transport)
        transport.__aexit__ = AsyncMock(return_value=False)

        seen: dict[str, Any] = {}

        def record(*args: Any, **kwargs: Any) -> Any:
            seen.update(kwargs)
            return transport

        with patch("httpx.AsyncClient", side_effect=record):
            await client.resolve(
                "https://contoso.sharepoint.com/sites/Reviews/a.docx",
                token="carlos-token",
            )

        assert seen["headers"]["Authorization"] == "Bearer carlos-token"


class TestRedactingALinkForLogs:
    """A sharing link grants access, so it must not survive into a log record.

    Logs widen the audience: the link was visible to one Teams channel, but a log
    record reaches ops dashboards and whatever ships them. What has to be kept is
    enough to debug a refusal -- which site the document turned out to be in.
    """

    def test_the_query_string_goes(self) -> None:
        """``?e=`` is the part that makes an anyone-with-the-link URL work."""

        assert redacted(
            "https://contoso.sharepoint.com/sites/Reviews/a.docx?d=w1&csf=1&e=SeCrEt"
        ) == "https://contoso.sharepoint.com/sites/Reviews/a.docx"

    def test_an_opaque_share_id_is_masked(self) -> None:
        """There is no path in this form -- the id *is* the credential."""

        assert redacted(
            "https://contoso.sharepoint.com/:w:/s/Reviews/EWabc123?e=xyz"
        ) == "https://contoso.sharepoint.com/:w:/s/[redacted]"

    def test_a_onedrive_share_id_is_masked_despite_looking_like_a_path(self) -> None:
        """The bug this file once asserted the opposite of.

        ``/:w:/g/personal/<user>/EWabc...`` is a share link whose id sits *after* two
        ordinary-looking segments, so exempting anything starting ``personal/`` handed
        the credential straight back.
        """

        assert redacted(
            "https://contoso-my.sharepoint.com/:w:/g/personal/x/EWabc123?e=xyz"
        ) == "https://contoso-my.sharepoint.com/:w:/g/[redacted]"

    def test_an_ordinary_path_is_kept(self) -> None:
        """The diagnostically useful case, and it names no secret."""

        for url in (
            "https://contoso.sharepoint.com/sites/Reviews/Drafts/a.docx",
            "https://contoso.sharepoint.com/:w:/r/sites/Reviews/Drafts/a.docx?e=1",
        ):
            assert "sites/Reviews/Drafts/a.docx" in redacted(url)

    def test_nothing_recognisable_reveals_nothing(self) -> None:
        assert redacted("not a url") == "[unparseable url]"

    @pytest.mark.parametrize(
        "form", ["s", "g", "p", "u", "b", "f", "t", "v", "w", "z"]
    )
    def test_no_share_id_survives_any_non_resource_form(self, form: str) -> None:
        """Every form but ``r``, including ones not yet seen, must mask.

        This test previously passed by omission -- it asserted the property over three
        URLs that happened to exclude the form that leaked. Enumerating the forms is
        what makes it mean anything, and an unknown letter is included on purpose:
        a form Microsoft adds later has to fail safe rather than pass through.
        """

        secret = "EWsecret123"
        for document_type in (":w:", ":x:", ":p:", ":u:", ":f:"):
            url = f"https://contoso.sharepoint.com/{document_type}/{form}/A/B/{secret}"
            assert secret not in redacted(url), url

    def test_a_secret_in_the_query_never_survives(self) -> None:
        """Whatever the path form, the query string is where tokens live."""

        secret = "EWsecret123"
        for url in (
            f"https://contoso.sharepoint.com/sites/Reviews/a.docx?sourcedoc={secret}",
            f"https://contoso.sharepoint.com/:w:/r/sites/R/a.docx?e={secret}",
            f"https://contoso.sharepoint.com/_layouts/15/Doc.aspx?sourcedoc={secret}",
        ):
            assert secret not in redacted(url), url

    def test_the_resource_form_is_the_only_one_kept(self) -> None:
        """Case-insensitively, since Teams is not consistent about it."""

        for url in (
            "https://contoso.sharepoint.com/:w:/r/sites/Reviews/Drafts/a.docx",
            "https://contoso.sharepoint.com/:W:/R/sites/Reviews/Drafts/a.docx",
        ):
            assert redacted(url).endswith("/sites/Reviews/Drafts/a.docx"), url

    def test_a_onedrive_resource_path_is_kept(self) -> None:
        """``/:w:/r/personal/...`` is a real path, so masking it would lose the site."""

        assert redacted(
            "https://contoso-my.sharepoint.com/:w:/r/personal/carlos/Documents/a.docx"
        ).endswith("/personal/carlos/Documents/a.docx")

    def test_a_fragment_goes_too(self) -> None:
        assert redacted(
            "https://contoso.sharepoint.com/sites/Reviews/a.docx#EWsecret123"
        ) == "https://contoso.sharepoint.com/sites/Reviews/a.docx"

    def test_userinfo_is_dropped(self) -> None:
        """Cannot arrive from Teams, but a log is the last place for a stray password."""

        assert redacted(
            "https://user:pw@contoso.sharepoint.com/sites/Reviews/a.docx"
        ) == "https://contoso.sharepoint.com/sites/Reviews/a.docx"

    def test_a_url_with_no_query_is_unchanged(self) -> None:
        plain = "https://contoso.sharepoint.com/sites/Reviews/a.docx"
        assert redacted(plain) == plain


class TestTheFallbackResolver:
    """Reached only when ``/shares`` will not resolve a URL that does have a path.

    It used to refuse anything from "Copy link", because ``/:w:/r/sites/X/...`` begins
    with ``:w:`` rather than ``sites``. Stripping the prefix first is all it needed.
    """

    def parts_of(self, url: str) -> list[str]:
        from urllib.parse import unquote

        from lib.services.microsoft.graph.client import _site_relative_path

        return [unquote(p) for p in _site_relative_path(url).split("/") if p]

    def test_a_copy_link_url_yields_a_site_and_path(self) -> None:
        assert self.parts_of(
            "https://contoso.sharepoint.com/:w:/r/sites/Reviews/Drafts/a.docx"
        ) == ["sites", "Reviews", "Drafts", "a.docx"]

    def test_a_plain_url_is_unaffected(self) -> None:
        assert self.parts_of(
            "https://contoso.sharepoint.com/sites/Reviews/Drafts/a.docx"
        ) == ["sites", "Reviews", "Drafts", "a.docx"]

    def test_case_is_preserved_because_graph_is_addressed_with_it(self) -> None:
        """Lowercasing here would ask Graph for a library that does not exist."""

        assert "Shared Documents" in self.parts_of(
            "https://contoso.sharepoint.com/:w:/r/sites/Reviews/Shared%20Documents/a.docx"
        )

    @pytest.mark.asyncio
    async def test_an_opaque_link_is_still_beyond_it(self) -> None:
        """Honest about the limit: there is no path in one, so ``/shares`` owns them."""

        missing = MagicMock(status_code=404)
        transport = MagicMock()
        transport.get = AsyncMock(return_value=missing)

        with pytest.raises(client.GraphError, match="cannot read a site and path"):
            await client._resolve_item(
                transport, "https://contoso.sharepoint.com/:w:/s/Reviews/EWabc123"
            )


class TestSegmentsThatCannotBeAddressed:
    """A path segment is decoded *after* the split, so ``%2F`` smuggles separators in.

    ``Drafts%2F..%2FSecret.docx`` is one segment when split and three once decoded, and
    interpolated into a Graph URL it addresses a document the link did not name. Graph
    still reads it as the asker, so the reach is bounded to what they can open -- but
    that is a bound, not a reason to allow it.
    """

    def graph(self) -> Any:
        """A transport that fails ``/shares``, forcing the fallback branch."""

        transport = MagicMock()
        transport.get = AsyncMock(return_value=MagicMock(status_code=404))
        return transport

    @pytest.mark.parametrize(
        "tail",
        [
            "Drafts%2F..%2F..%2FSecret.docx",  # the reported case
            "Drafts%2FSecret.docx",  # a separator alone is enough
            "..",  # a literal dot-segment
            ".",
            "%2e%2e",  # encoded dot-segment
            "Drafts%5C..%5CSecret.docx",  # backslash, for a Windows-flavoured path
            "a%00b.docx",  # a null byte
            "a%0Ab.docx",  # a newline, which would forge a log line
        ],
    )
    @pytest.mark.asyncio
    async def test_it_is_refused(self, tail: str) -> None:
        with pytest.raises(client.GraphError, match="cannot be addressed safely"):
            await client._resolve_item(
                self.graph(),
                f"https://contoso.sharepoint.com/sites/Reviews/Lib/{tail}",
            )

    @pytest.mark.asyncio
    async def test_the_refusal_does_not_echo_the_segment(self) -> None:
        """It is attacker-controlled text; the message goes back to a chat."""

        with pytest.raises(client.GraphError) as raised:
            await client._resolve_item(
                self.graph(),
                "https://contoso.sharepoint.com/sites/Reviews/Lib/a%2F..%2Fb.docx",
            )

        assert ".." not in str(raised.value)


class TestBuildingTheGraphPath:
    """What reaches Graph must be the document the link named, exactly.

    Segments are re-encoded rather than interpolated raw: httpx reads a decoded ``#``
    as a fragment and ``?`` as a query, either of which silently truncates the path and
    addresses something else.
    """

    async def resolved_urls(self, url: str) -> list[str]:
        """Every URL the resolver asked Graph for, in order."""

        site = MagicMock(status_code=200)
        site.json.return_value = {"id": "site-1"}
        item = MagicMock(status_code=200)
        item.json.return_value = {"name": "a.docx"}

        calls: list[str] = []

        async def get(requested: str, **_: Any) -> Any:
            calls.append(requested)
            if "/shares/" in requested:
                return MagicMock(status_code=404)
            return site if requested.endswith(("Reviews", "Reviews/")) else item

        transport = MagicMock()
        transport.get = get
        await client._resolve_item(transport, url)
        return calls

    @pytest.mark.asyncio
    async def test_a_hash_in_a_file_name_cannot_end_the_path(self) -> None:
        urls = await self.resolved_urls(
            "https://contoso.sharepoint.com/sites/Reviews/Lib/Draft%232.docx"
        )

        assert "%23" in urls[-1], "the hash must be sent encoded"
        addressed = httpx.URL(urls[-1])
        assert addressed.fragment == "", "a fragment means the path was truncated"
        # Decoded, it is exactly the name the link gave -- nothing lost, nothing moved.
        assert addressed.path.endswith("/Draft#2.docx")

    @pytest.mark.asyncio
    async def test_a_question_mark_cannot_start_a_query(self) -> None:
        urls = await self.resolved_urls(
            "https://contoso.sharepoint.com/sites/Reviews/Lib/Is%20this%20it%3F.docx"
        )

        assert "%3F" in urls[-1], "the question mark must be sent encoded"
        addressed = httpx.URL(urls[-1])
        assert addressed.query == b"", "a query means the path was truncated"
        assert addressed.path.endswith("/Is this it?.docx")

    @pytest.mark.asyncio
    async def test_an_ordinary_name_with_a_space_still_resolves(self) -> None:
        """The common case, and the one an over-eager guard would break."""

        urls = await self.resolved_urls(
            "https://contoso.sharepoint.com/sites/Reviews/Lib/My%20Draft.docx"
        )

        assert httpx.URL(urls[-1]).path.endswith("/My Draft.docx")

    @pytest.mark.asyncio
    async def test_a_copy_link_url_reaches_the_same_document(self) -> None:
        """The fix from the previous round, now asserted end to end."""

        urls = await self.resolved_urls(
            "https://contoso.sharepoint.com/:w:/r/sites/Reviews/Lib/a.docx?e=1"
        )

        assert httpx.URL(urls[-1]).path.endswith("/a.docx")
