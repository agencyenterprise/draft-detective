"""Keep the reference downloader's direct fetches on the public internet.

The URLs it fetches come from the user's document, or from an agent reading it, so
they are attacker-controlled. Fetched from inside the deployment, a URL naming a
private, loopback or link-local address would reach services that are not meant to
be reachable from outside (cloud metadata, cluster services, an intranet), and a PDF
answer would come back as a project file.

Every request the direct client makes, including each redirect hop, goes through
``refuse_non_public``: the host must resolve, and every address it resolves to must
be globally routable.

A host this pod cannot resolve is neither refused nor fetched directly: it raises
``UnresolvableHostError``, which the caller treats like any other direct-fetch
failure and hands to Jina. Behind an egress proxy the pod may not resolve public
names at all, and Jina fetches from its own network, so nothing internal is exposed
that way.

Not covered: DNS rebinding between this check and httpx's own resolution. Closing
it would need a transport that connects to the address checked here.
"""

import asyncio
import ipaddress
import socket

import httpx

ALLOWED_SCHEMES = ("http", "https")

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class BlockedUrlError(Exception):
    """The URL points somewhere a direct fetch must not go."""


class UnresolvableHostError(Exception):
    """This pod cannot resolve the URL's host."""


async def refuse_non_public(request: httpx.Request) -> None:
    """httpx request hook: raise unless the request goes to a public address."""

    url = request.url
    if url.scheme not in ALLOWED_SCHEMES:
        raise BlockedUrlError(f"scheme {url.scheme!r} is not allowed")
    if not url.host:
        raise BlockedUrlError("the URL has no host")

    for address in await _addresses(url.host, url.port or _default_port(url.scheme)):
        if not _is_public(address):
            raise BlockedUrlError(f"{url.host} resolves to a non-public address")


async def _addresses(host: str, port: int) -> list[IPAddress]:
    """The host's addresses: itself when it is an IP literal, else what DNS says."""

    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        resolved = await _resolve(host, port)
    except (socket.gaierror, UnicodeError) as error:
        raise UnresolvableHostError(f"could not resolve {host}: {error}") from error
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
