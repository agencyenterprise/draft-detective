"""The reference downloader never fetches a private, loopback or link-local address.

Its URLs come from the user's document, so each test plays an attacker pointing it
inside the deployment, directly or through a redirect.
"""

import asyncio
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lib.workflows.context import ContextSchema
from lib.workflows.reference_downloader.tools import download_file_from_url as dl
from lib.workflows.reference_downloader.tools import url_guard

PDF = b"%PDF-1.7 internal report"
PUBLIC_IP = "93.184.215.14"
JINA_HOST = "r.jina.ai"

# Hosts the fake DNS knows; any other name does not resolve.
DNS = {
    "publisher.example.org": [PUBLIC_IP],
    "attacker.example.net": [PUBLIC_IP],
    "intranet.example.org": ["10.1.2.3"],
    "split.example.org": [PUBLIC_IP, "127.0.0.1"],
    JINA_HOST: [PUBLIC_IP],
}


class FakeWeb:
    """Answers every request with a PDF, except a redirect from the attacker's host."""

    def __init__(self, redirect_to: str | None = None) -> None:
        self.redirect_to = redirect_to
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        # Routed by the Host header: a pinned request is addressed to an IP.
        self.requests.append(request)
        host = request.headers["host"]
        if host == JINA_HOST:
            return httpx.Response(200, text="# markdown")
        if self.redirect_to and host == "attacker.example.net":
            return httpx.Response(302, headers={"Location": self.redirect_to})
        return httpx.Response(
            200, content=PDF, headers={"Content-Type": "application/pdf"}
        )

    @property
    def hosts(self) -> list[str]:
        return [request.headers["host"] for request in self.requests]


async def _fake_resolve(host: str, port: int) -> list[str]:
    if host not in DNS:
        raise url_guard.socket.gaierror(8, "nodename nor servname provided")
    return DNS[host]


@pytest.fixture
def web(tmp_path: Path) -> Iterator[Callable[..., FakeWeb]]:
    """Route httpx through a FakeWeb, with fake DNS and no database."""
    webs: list[FakeWeb] = []
    real_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        mock = httpx.MockTransport(webs[0].handle)
        transport = kwargs.pop("transport", None)
        if isinstance(transport, url_guard.PinnedTransport):
            transport.inner = mock
        return real_client(transport=transport or mock, **kwargs)

    with (
        patch.object(dl.httpx, "AsyncClient", client_factory),
        patch.object(dl.jina_rate_limiter, "aacquire", AsyncMock(return_value=True)),
        patch.object(dl.config, "FILE_UPLOADS_MOUNT_PATH", str(tmp_path)),
        patch.object(dl, "_persist_file_record", AsyncMock(return_value="file-1")),
        patch.object(url_guard, "_resolve", _fake_resolve),
    ):

        def _install(**kwargs: Any) -> FakeWeb:
            webs.append(FakeWeb(**kwargs))
            return webs[0]

        yield _install


def _context() -> ContextSchema:
    return ContextSchema.model_construct(
        project_id=str(uuid.uuid4()), user_id=str(uuid.uuid4())
    )


async def _download(url: str) -> dl.DownloadFileFromUrlResponse:
    return await dl._download_file_from_url_async(url, "A reference", _context())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        pytest.param("http://127.0.0.1:8000/api/health", id="loopback"),
        pytest.param("http://localhost/", id="localhost-literal-name"),
        pytest.param("http://169.254.169.254/latest/meta-data/", id="cloud-metadata"),
        pytest.param("http://10.0.0.5/report.pdf", id="private-v4"),
        pytest.param("http://[::1]/", id="loopback-v6"),
        pytest.param("http://[::ffff:127.0.0.1]/", id="v4-mapped-v6"),
        pytest.param("http://[64:ff9b::a9fe:a9fe]/", id="nat64-to-metadata"),
        pytest.param("http://[64:ff9b::a01:203]/", id="nat64-to-private"),
        pytest.param("http://[::7f00:1]/", id="v4-compatible-v6"),
        pytest.param("http://intranet.example.org/report.pdf", id="name-to-private"),
        pytest.param("http://split.example.org/report.pdf", id="name-to-mixed"),
    ],
)
async def test_internal_url_is_refused_without_any_fetch(
    web: Callable[..., FakeWeb], url: str
) -> None:
    fake = web()
    with patch.dict(DNS, {"localhost": ["127.0.0.1"]}):
        response = await _download(url)

    assert response.success is False
    assert response.file_id is None
    assert "private or internal address" in response.message
    # Neither fetched directly nor handed to Jina.
    assert fake.requests == []


@pytest.mark.asyncio
async def test_redirect_into_the_deployment_is_refused(
    web: Callable[..., FakeWeb],
) -> None:
    fake = web(redirect_to="http://169.254.169.254/latest/report.pdf")

    response = await _download("https://attacker.example.net/paper.pdf")

    assert response.success is False
    assert "private or internal address" in response.message
    assert fake.hosts == ["attacker.example.net"]


@pytest.mark.asyncio
async def test_public_pdf_is_still_downloaded(web: Callable[..., FakeWeb]) -> None:
    fake = web()

    response = await _download("https://publisher.example.org/paper.pdf")

    assert response.success is True
    assert response.file_id == "file-1"
    assert fake.hosts == ["publisher.example.org"]


@pytest.mark.asyncio
async def test_connection_goes_to_the_checked_address(
    web: Callable[..., FakeWeb],
) -> None:
    fake = web()

    await _download("https://publisher.example.org/paper.pdf")

    [sent] = fake.requests
    assert sent.url.host == PUBLIC_IP
    assert sent.headers["host"] == "publisher.example.org"
    assert sent.extensions["sni_hostname"] == "publisher.example.org"


@pytest.mark.asyncio
async def test_dns_rebinding_after_the_hook_is_refused(
    web: Callable[..., FakeWeb],
) -> None:
    """Public for the hook's lookup, loopback for the connection's: refused."""
    fake = web()
    answers = iter([[PUBLIC_IP], ["127.0.0.1"]])

    async def rebinding(host: str, port: int) -> list[str]:
        return next(answers)

    with patch.object(url_guard, "_resolve", rebinding):
        response = await _download("https://rebind.example.net/paper.pdf")

    assert response.success is False
    assert "private or internal address" in response.message
    assert fake.requests == []


@pytest.mark.asyncio
async def test_idn_host_is_checked_in_the_form_httpx_connects_to(
    web: Callable[..., FakeWeb],
) -> None:
    """IDNA 2003 maps faß to fass; httpx connects to the IDNA 2008 xn-- name."""
    fake = web()
    names = {
        "fass.attacker.example": [PUBLIC_IP],
        "xn--fa-hia.attacker.example": ["10.0.0.7"],
    }

    with patch.dict(DNS, names):
        response = await _download("https://faß.attacker.example/paper.pdf")

    assert response.success is False
    assert fake.requests == []


@pytest.mark.asyncio
async def test_stalled_dns_lookup_goes_to_jina(web: Callable[..., FakeWeb]) -> None:
    fake = web()

    async def stalled(host: str, port: int) -> list[str]:
        if host == JINA_HOST:
            return [PUBLIC_IP]
        await asyncio.sleep(10)
        return [PUBLIC_IP]

    with (
        patch.object(url_guard, "_resolve", stalled),
        patch.object(url_guard, "DNS_TIMEOUT_SECONDS", 0.05),
    ):
        response = await _download("https://slow-dns.example.org/paper")

    assert response.success is True
    assert fake.hosts == [JINA_HOST]


@pytest.mark.asyncio
async def test_host_this_pod_cannot_resolve_goes_to_jina(
    web: Callable[..., FakeWeb],
) -> None:
    fake = web()

    response = await _download("https://behind-a-proxy.example.com/paper")

    assert response.success is True
    assert fake.hosts == [JINA_HOST]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["ftp://publisher.example.org/x", "file:///etc/passwd"])
async def test_non_http_scheme_is_refused(url: str) -> None:
    with pytest.raises(url_guard.BlockedUrlError):
        await url_guard.refuse_non_public(httpx.Request("GET", url))
