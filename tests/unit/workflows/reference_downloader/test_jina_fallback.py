"""Any direct-fetch failure falls back to Jina, and Jina is called at most once."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lib.workflows.reference_downloader.tools import download_file_from_url as dl

URL = "https://publisher.example.org/paper"
JINA_HOST = "r.jina.ai"
PDF_BYTES = b"%PDF-1.7 fake pdf body"
MARKDOWN = "# Paper title\n\nFull text."

Handler = Callable[[httpx.Request], httpx.Response]


class FakeWeb:
    """Routes requests to a direct-fetch handler or a Jina handler, recording each."""

    def __init__(self, direct: Handler, jina: Handler) -> None:
        self.direct = direct
        self.jina = jina
        self.direct_calls = 0
        self.jina_calls = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == JINA_HOST:
            self.jina_calls += 1
            return self.jina(request)
        self.direct_calls += 1
        return self.direct(request)


def _raise(exc_type: type[httpx.TransportError]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc_type("blocked", request=request)

    return handler


def _respond(
    status: int, content: bytes | str = b"", content_type: str = ""
) -> Handler:
    headers = {"Content-Type": content_type} if content_type else {}
    return lambda request: httpx.Response(status, content=content, headers=headers)


JINA_OK = _respond(200, MARKDOWN, "text/plain")


@pytest.fixture
def install(tmp_path: Path) -> Iterator[Callable[[FakeWeb], FakeWeb]]:
    """Point every httpx client at a FakeWeb, stub the rate limiter, save to tmp_path."""
    web: list[FakeWeb] = []
    real_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(web[0].handle), **kwargs)

    with (
        patch.object(dl.httpx, "AsyncClient", client_factory),
        patch.object(dl.jina_rate_limiter, "aacquire", AsyncMock(return_value=True)),
        patch.object(dl.config, "FILE_UPLOADS_MOUNT_PATH", str(tmp_path)),
    ):

        def _install(fake: FakeWeb) -> FakeWeb:
            web.append(fake)
            return fake

        yield _install


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "direct",
    [
        pytest.param(_raise(httpx.ConnectError), id="connect-error"),
        pytest.param(_raise(httpx.ConnectTimeout), id="connect-timeout"),
        pytest.param(_raise(httpx.ReadTimeout), id="read-timeout"),
        pytest.param(_respond(403, "Access denied"), id="http-403"),
        pytest.param(_respond(200, b"", "application/pdf"), id="empty-pdf"),
    ],
)
async def test_direct_failure_falls_back_to_jina(
    install: Callable[[FakeWeb], FakeWeb], tmp_path: Path, direct: Handler
) -> None:
    web = install(FakeWeb(direct=direct, jina=JINA_OK))

    saved = await dl._download_direct_url(URL)

    assert saved is not None
    assert saved.content_type == "text/markdown"
    assert (tmp_path / saved.filename).read_text() == MARKDOWN
    assert (web.direct_calls, web.jina_calls) == (1, 1)


@pytest.mark.asyncio
async def test_direct_pdf_is_saved_without_jina(
    install: Callable[[FakeWeb], FakeWeb], tmp_path: Path
) -> None:
    web = install(
        FakeWeb(direct=_respond(200, PDF_BYTES, "application/pdf"), jina=JINA_OK)
    )

    saved = await dl._download_direct_url(URL)

    assert saved is not None
    assert saved.content_type == "application/pdf"
    assert (tmp_path / saved.filename).read_bytes() == PDF_BYTES
    assert web.jina_calls == 0


@pytest.mark.asyncio
async def test_non_pdf_uses_jina_once_even_when_jina_fails(
    install: Callable[[FakeWeb], FakeWeb],
) -> None:
    web = install(
        FakeWeb(
            direct=_respond(200, "<html></html>", "text/html"),
            jina=_respond(502, "Bad gateway"),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await dl._download_direct_url(URL)

    assert web.jina_calls == 1


@pytest.mark.asyncio
async def test_tool_reports_failure_when_direct_and_jina_are_both_blocked(
    install: Callable[[FakeWeb], FakeWeb],
) -> None:
    web = install(
        FakeWeb(direct=_raise(httpx.ConnectError), jina=_raise(httpx.ConnectError))
    )

    response = await dl._download_file_from_url_async(
        URL, "Some reference", MagicMock()
    )

    assert response.success is False
    assert response.file_id is None
    assert (web.direct_calls, web.jina_calls) == (1, 1)
