"""Keep the reference downloader's direct fetches on the public internet.

The URLs it fetches come from the user's document, or from an agent reading it, so
they are attacker-controlled. Fetched from inside the deployment, a URL naming a
private, loopback or link-local address would reach services that are not meant to
be reachable from outside (cloud metadata, cluster services, an intranet), and a PDF
answer would come back as a project file.

Two pieces, both applied to every request the direct client sends, redirect hops
included:

- ``PinnedTransport`` resolves the host, requires every address to be globally
  routable, and then connects to the address it checked, keeping the original
  ``Host`` header and TLS server name. Checking one lookup and letting the
  connection make another would let a DNS server answer differently the second
  time (DNS rebinding).
- ``refuse_non_public``, a request hook, runs the same check on every request.

``direct_client`` builds the client. httpx stops reading the environment's proxy
settings (``HTTPS_PROXY``, ``NO_PROXY`` and the like) once it is given a transport,
and a deploy that sets them may need the proxy to reach the internet. So the client
mounts a proxy transport wherever httpx itself would use one, from httpx's own
reading of those settings, and ``PinnedTransport`` takes every other request,
``NO_PROXY`` hosts included. A proxied request is checked by the hook but not
pinned: the proxy connects, and its own egress policy governs where.

Names are resolved in the ASCII form httpx connects to (``raw_host``), not the
Unicode one, whose IDNA encoding can differ and name another host.

A host this pod cannot resolve, or not in time, is neither refused nor fetched
directly: it raises ``UnresolvableHostError``, which the caller treats like any
other direct-fetch failure and hands to Jina. Behind an egress proxy the pod may not
resolve public names at all, and Jina fetches from its own network, so nothing
internal is exposed that way.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from typing import Any

import httpx

# Private, but it is exactly how httpx reads the proxy environment, NO_PROXY
# patterns included; re-deriving it here would drift from what httpx would do.
from httpx._utils import get_environment_proxies

ALLOWED_SCHEMES = ("http", "https")
# httpx's own timeout does not cover the lookup, which runs before it connects.
DNS_TIMEOUT_SECONDS = 10.0

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class BlockedUrlError(Exception):
    """The URL points somewhere a direct fetch must not go."""


class UnresolvableHostError(Exception):
    """This pod cannot resolve the URL's host."""


def direct_client(**kwargs: Any) -> httpx.AsyncClient:
    """An httpx client whose every request, redirects included, is held to public
    addresses: pinned to them, or only checked when an environment proxy connects."""

    proxies: dict[str, httpx.AsyncBaseTransport | None] = {
        pattern: None if proxy is None else httpx.AsyncHTTPTransport(proxy=proxy)
        for pattern, proxy in get_environment_proxies().items()
    }
    return httpx.AsyncClient(
        transport=PinnedTransport(),
        mounts=proxies,
        event_hooks={"request": [refuse_non_public]},
        **kwargs,
    )


class PinnedTransport(httpx.AsyncBaseTransport):
    """Sends each request to a public address its host was checked to have.

    Each checked address is tried in turn until one connects, as httpx would try
    every address it resolved itself: a dual-stack host's first answer is often an
    IPv6 address an IPv4-only pod cannot reach.

    Each origin gets its own connection pool. A pinned request's URL names an IP,
    which is what httpcore keys its pool on, so two hostnames sharing an address
    would otherwise share a keep-alive connection, and the second would skip the TLS
    handshake that checks its own hostname.
    """

    def __init__(
        self,
        new_inner: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    ) -> None:
        self.new_inner = new_inner
        self._pools: dict[tuple[str, str, int | None], httpx.AsyncBaseTransport] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        *others, last = await public_addresses(request.url)
        pool = self._pool_for(request.url)
        for address in others:
            try:
                return await pool.handle_async_request(_pinned(request, address))
            except (httpx.ConnectError, httpx.ConnectTimeout):
                continue
        return await pool.handle_async_request(_pinned(request, last))

    def _pool_for(self, url: httpx.URL) -> httpx.AsyncBaseTransport:
        origin = (url.scheme, url.raw_host.decode("ascii").lower(), url.port)
        if origin not in self._pools:
            self._pools[origin] = self.new_inner()
        return self._pools[origin]

    async def aclose(self) -> None:
        for pool in self._pools.values():
            await pool.aclose()


async def refuse_non_public(request: httpx.Request) -> None:
    """httpx request hook: raise unless the request goes to a public address."""

    await public_addresses(request.url)


async def public_addresses(url: httpx.URL) -> list[IPAddress]:
    """Every address the URL's host resolves to, all of them public, or raise."""

    if url.scheme not in ALLOWED_SCHEMES:
        raise BlockedUrlError(f"scheme {url.scheme!r} is not allowed")
    host = url.raw_host.decode("ascii")
    if not host:
        raise BlockedUrlError("the URL has no host")

    addresses = await _addresses(host, url.port or _default_port(url.scheme))
    for address in addresses:
        if not _is_public(address):
            raise BlockedUrlError(f"{host} resolves to a non-public address")
    return addresses


def _pinned(request: httpx.Request, address: IPAddress) -> httpx.Request:
    """The request addressed to ``address``, still naming its host to the server."""

    extensions = dict(request.extensions)
    if request.url.scheme == "https":
        extensions["sni_hostname"] = request.url.raw_host.decode("ascii")
    return httpx.Request(
        request.method,
        request.url.copy_with(host=str(address)),
        headers=request.headers,
        stream=request.stream,
        extensions=extensions,
    )


async def _addresses(host: str, port: int) -> list[IPAddress]:
    """The host's addresses: itself when it is an IP literal, else what DNS says."""

    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        resolved = await asyncio.wait_for(
            _resolve(host, port), timeout=DNS_TIMEOUT_SECONDS
        )
    except (socket.gaierror, UnicodeError, TimeoutError) as error:
        raise UnresolvableHostError(f"could not resolve {host}: {error!r}") from error
    if not resolved:
        raise UnresolvableHostError(f"{host} resolved to no addresses")
    return [ipaddress.ip_address(address) for address in resolved]


async def _resolve(host: str, port: int) -> list[str]:
    """Every address DNS gives for the host, as strings."""

    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )
    return [str(info[4][0]) for info in infos]


def _is_public(address: IPAddress) -> bool:
    """Globally routable, judging an IPv6 address that embeds an IPv4 one by that."""

    if isinstance(address, ipaddress.IPv6Address):
        address = _embedded_ipv4(address) or address
    return address.is_global and not address.is_multicast


# NAT64 (RFC 6052) reaches the IPv4 address in its low 32 bits through a gateway,
# and Python counts the whole prefix as global.
_NAT64 = ipaddress.IPv6Network("64:ff9b::/96")
# Deprecated IPv4-compatible addresses (``::a.b.c.d``), also counted as global.
_IPV4_COMPATIBLE = ipaddress.IPv6Network("::/96")


def _embedded_ipv4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv4-mapped, NAT64 or IPv4-compatible address leads to."""

    if address.ipv4_mapped:
        return address.ipv4_mapped
    if address in _NAT64 or (address in _IPV4_COMPATIBLE and int(address) > 1):
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return None


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80
