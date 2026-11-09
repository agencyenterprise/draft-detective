"""Any direct-fetch failure falls back to Jina, and Jina is called at most once."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lib.workflows.reference_downloader.tools import direct_fetch, url_guard
from lib.workflows.reference_downloader.tools import download_file_from_url as dl

URL = "https://publisher.example.org/paper"
JINA_HOST = "r.jina.ai"
PDF_BYTES = b"%PDF-1.7 fake pdf body"
MARKDOWN = "# Paper title\n\nFull text."
PUBLIC_IP = "93.184.215.14"

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
        mock = httpx.MockTransport(web[0].handle)
        transport = kwargs.pop("transport", None)
        if isinstance(transport, url_guard.PinnedTransport):
            transport.new_inner = lambda: mock
        # A proxy mount answers from the same mock, addressed to the original host.
        mounts = kwargs.pop("mounts", None) or {}
        kwargs["mounts"] = {k: None if v is None else mock for k, v in mounts.items()}
        return real_client(transport=transport or mock, **kwargs)

    with (
        patch.object(dl.httpx, "AsyncClient", client_factory),
        patch.object(dl.jina_rate_limiter, "aacquire", AsyncMock(return_value=True)),
        patch.object(dl.config, "FILE_UPLOADS_MOUNT_PATH", str(tmp_path)),
        # No real DNS in tests: every host resolves to a public address.
        # No proxy unless a test sets one: on macOS this reads system settings too.
        patch.object(url_guard, "get_environment_proxies", return_value={}),
        patch.object(url_guard, "_resolve", AsyncMock(return_value=[PUBLIC_IP])),
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


@pytest.mark.asyncio
async def test_tool_reports_failure_when_the_file_record_cannot_be_saved(
    install: Callable[[FakeWeb], FakeWeb],
) -> None:
    install(FakeWeb(direct=_respond(200, PDF_BYTES, "application/pdf"), jina=JINA_OK))
    context = MagicMock(project_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))

    with patch.object(dl, "create_file_record", AsyncMock(side_effect=RuntimeError)):
        response = await dl._download_file_from_url_async(
            URL, "Some reference", context
        )

    assert response.success is False
    assert response.file_id is None


class _Drip:
    """A response body served chunk by chunk, counting how many chunks were read."""

    def __init__(
        self, chunks: int, chunk_size: int, content_type: str, pause: float = 0
    ) -> None:
        self.chunks = chunks
        self.chunk_size = chunk_size
        self.content_type = content_type
        self.pause = pause
        self.served = 0

    async def _body(self) -> AsyncIterator[bytes]:
        for _ in range(self.chunks):
            self.served += 1
            await asyncio.sleep(self.pause)
            yield b"%" * self.chunk_size

    def __call__(self, request: httpx.Request) -> httpx.Response:
        headers = {"Content-Type": self.content_type}
        return httpx.Response(200, content=self._body(), headers=headers)


@pytest.mark.asyncio
async def test_oversized_pdf_is_not_read_past_the_limit(
    install: Callable[[FakeWeb], FakeWeb], tmp_path: Path
) -> None:
    body = _Drip(chunks=100, chunk_size=1024, content_type="application/pdf")
    web = install(FakeWeb(direct=body, jina=JINA_OK))

    with patch.object(direct_fetch, "MAX_DIRECT_DOWNLOAD_BYTES", 4 * 1024):
        saved = await dl._download_direct_url(URL)

    assert body.served <= 5
    assert saved.content_type == "text/markdown"
    assert not list(tmp_path.glob("*.pdf"))
    assert web.jina_calls == 1


@pytest.mark.asyncio
async def test_non_pdf_body_is_left_unread(
    install: Callable[[FakeWeb], FakeWeb],
) -> None:
    body = _Drip(chunks=100, chunk_size=1024, content_type="text/html")
    web = install(FakeWeb(direct=body, jina=JINA_OK))

    saved = await dl._download_direct_url(URL)

    assert body.served <= 1
    assert saved.content_type == "text/markdown"
    assert web.jina_calls == 1


@pytest.mark.asyncio
async def test_slow_pdf_is_abandoned_at_the_deadline(
    install: Callable[[FakeWeb], FakeWeb], tmp_path: Path
) -> None:
    body = _Drip(chunks=100, chunk_size=1, content_type="application/pdf", pause=0.05)
    web = install(FakeWeb(direct=body, jina=JINA_OK))

    with patch.object(direct_fetch, "DIRECT_DOWNLOAD_DEADLINE_SECONDS", 0.3):
        saved = await dl._download_direct_url(URL)

    assert body.served < 100
    assert saved.content_type == "text/markdown"
    assert not list(tmp_path.glob("*.pdf"))
    assert web.jina_calls == 1


@pytest.mark.asyncio
async def test_error_answer_keeps_its_body_for_the_log(
    install: Callable[[FakeWeb], FakeWeb],
) -> None:
    install(FakeWeb(direct=_respond(403, "Access denied", "text/plain"), jina=JINA_OK))

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await direct_fetch.fetch_pdf_directly(URL)

    assert raised.value.response.status_code == 403
    assert "body='Access denied'" in dl._describe_error(raised.value)
