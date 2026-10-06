"""Reading SharePoint documents through Graph.

Draft Detective is asked about documents from places that have no Word session to
borrow -- a Teams channel, most of all -- so the backend has to load them itself:
resolving a SharePoint URL to a drive item, and downloading its bytes.

**Every read is done as the person who asked.** ``resolve`` and ``download`` take that
person's bearer token -- obtained when they sign in to the Teams bot, see
``lib/services/microsoft/teams/sign_in.py`` -- so Graph applies their own permissions,
and a document they cannot open comes back 403 or 404. The bot is never a more
privileged reader than the person asking.

Two things were established by probing a real tenant rather than from documentation:

- A delegated token minted *by the server* is refused when Conditional Access
  requires a compliant device (AADSTS530035), because a server has no device
  identity. The user's token comes from a sign-in in their own browser instead,
  which is why the bot asks them to sign in.
- Graph serves whatever SharePoint last persisted. Under AutoSave that trails a
  live edit by about half a second, but with nobody editing it is simply current.

Writing is deliberately absent. A whole-file PUT is refused with 423 while anyone
has the document open, whatever identity asks, so writes belong to a Word client --
see ``lib/services/microsoft/word/word_package.py`` and the add-in.
"""

import base64
import logging
import re
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx


logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"

# The ``/:w:/r/`` that "Copy link" puts in front of an otherwise ordinary path. The
# second letter is the *form*, and it decides whether what follows is a path at all.
_SHARING_PREFIX = re.compile(r"^/:[a-z]:/(?P<form>[a-z])/", re.I)

# Of the forms Microsoft emits, only ``r`` ("resource") embeds the document's real
# path. ``s``, ``g``, ``p`` and ``u`` carry an opaque share id in its place. Anything
# unrecognised is treated as opaque as well, so a form added later fails safe.
_PATH_BEARING_FORM = "r"

class GraphError(Exception):
    """Raised when Graph will not give us what we asked for."""


def _site_relative_path(url: str) -> str:
    """A URL's path with any sharing prefix stripped.

    "Copy link" in Word and Teams produces ``/:w:/r/sites/X/...`` rather than the
    plain ``/sites/X/...``. Same site, same document; only the prefix differs, and
    walking the path without removing it would fail on the very link someone pasted
    from Word itself.

    Case is preserved, because this is used to address Graph and a document library's
    name is not case-insensitive there.
    """

    return _SHARING_PREFIX.sub("/", urlparse(url).path)


def redacted(url: str) -> str:
    """A SharePoint URL with the part that grants access removed, for logging.

    A sharing link is a bearer credential rather than merely an address: an "anyone
    with the link" URL is openable by whoever holds it, and what makes that work is
    the ``?e=`` token in the query string together with the opaque id in a
    ``/:w:/s/Site/EWabc...`` path.

    That matters for logs specifically because logs *widen* the audience. The link was
    already visible to one Teams channel; a log record reaches ops dashboards and
    whatever aggregator ships them, none of whom were in that channel.

    So the query string always goes. What survives is decided by the sharing *form*
    rather than by what the path looks like: only ``r`` embeds a real path, which is
    worth keeping because it is the part that tells you where a refused read pointed
    and it names no secret. Every other form is reduced to its shape.

    Keying on the form matters. An earlier version exempted any path beginning
    ``sites/`` or ``personal/``, which handed back the share id in
    ``/:w:/g/personal/<user>/EWabc...`` -- an OneDrive share link, where those segments
    precede the credential rather than replacing it.

    >>> redacted("https://x.sharepoint.com/:w:/r/sites/Reviews/Drafts/a.docx?e=1")
    'https://x.sharepoint.com/:w:/r/sites/Reviews/Drafts/a.docx'
    >>> redacted("https://x.sharepoint.com/:w:/g/personal/carlos/EWabc123?e=xyz")
    'https://x.sharepoint.com/:w:/g/[redacted]'
    """

    parsed = urlparse(url)
    if not parsed.netloc:
        return "[unparseable url]"

    # Any userinfo goes with it. A SharePoint link never carries one, but a log record
    # is the last place a stray credential should turn up.
    host = parsed.netloc.rsplit("@", 1)[-1]

    prefix = _SHARING_PREFIX.match(parsed.path)
    if prefix and prefix.group("form").lower() != _PATH_BEARING_FORM:
        # What follows the prefix is the share id, whatever it happens to look like.
        return f"{parsed.scheme}://{host}{prefix.group(0)}[redacted]"
    return f"{parsed.scheme}://{host}{parsed.path}"


def _is_addressable(segment: str) -> bool:
    """Whether a decoded path segment names one thing rather than moving the path.

    Read after ``unquote``, which is the point: ``%2F`` and ``%5C`` become separators
    only once decoded, so a segment written as ``Drafts%2F..%2FSecret.docx`` arrives
    here as three. Interpolated into a Graph URL it would address a document the link
    did not name.

    Refused rather than repaired. SharePoint permits neither a separator nor a
    bare dot-segment in a name, so a link that needs one is not a link to a document.
    Control characters go too -- a newline in a log record is its own problem.
    """

    if segment in (".", ".."):
        return False
    if "/" in segment or "\\" in segment:
        return False
    return not any(ord(character) < 0x20 for character in segment)


def _share_id(url: str) -> str:
    """Graph's encoding for "the item at this URL"."""

    encoded = base64.b64encode(url.encode("utf-8")).decode("ascii")
    return "u!" + encoded.rstrip("=").replace("/", "_").replace("+", "-")


async def resolve(url: str, *, token: str) -> dict[str, Any]:
    """The drive item for a SharePoint URL, if this identity may read it.

    ``token`` is whose reading this is, and it is required rather than defaulted:
    Graph refuses a document that person cannot open, which is the real permission
    check.

    ``/shares`` is the documented shortcut; walking site then path is the fallback,
    because a URL that has been through a chat message does not always decode back to
    the exact stored name.
    """

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        item = await _resolve_item(client, url)

    canonical = str(item.get("webUrl") or url)
    logger.info("resolved %s to %s", redacted(url), redacted(canonical))
    return item


async def _resolve_item(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    """The drive item, by whichever route Graph will give it up. No authorisation."""

    shared = await client.get(f"{GRAPH}/shares/{_share_id(url)}/driveItem")
    if shared.status_code == 200:
        return dict(shared.json())
    logger.info(
        "/shares did not resolve %s (%s)", redacted(url), shared.status_code
    )

    parsed = urlparse(url)
    # The sharing prefix has to go before the path is read as a path: "Copy link"
    # produces ``/:w:/r/sites/X/...``, whose first segment is ``:w:`` rather than
    # ``sites``, so this branch used to refuse a link the other branch handles fine.
    # An opaque ``/:w:/s/Site/EWabc...`` link is still beyond it -- there is no path
    # in one to walk -- and that is what ``/shares`` above is for.
    parts = [unquote(p) for p in _site_relative_path(url).split("/") if p]
    if len(parts) < 4 or parts[0].lower() != "sites":
        raise GraphError(f"cannot read a site and path out of {parsed.path}")

    unaddressable = [part for part in parts if not _is_addressable(part)]
    if unaddressable:
        # ``repr`` rather than the raw value: this is attacker-controlled text on its
        # way into a log, and a control character in one is how a log gets forged.
        logger.warning("refusing a link with unaddressable segments: %r", unaddressable)
        raise GraphError("that link's path cannot be addressed safely")

    site = await client.get(
        f"{GRAPH}/sites/{parsed.netloc}:/{quote(parts[0])}/{quote(parts[1])}"
    )
    if site.status_code != 200:
        raise GraphError(
            f"could not resolve the site: {site.status_code} {site.text[:200]}"
        )
    site_id = site.json()["id"]

    # parts[2] is the document library; the rest is the path inside its drive. Each
    # segment is re-encoded rather than interpolated raw, because a decoded ``#`` or
    # ``?`` in a file name ends the path component and would silently address
    # something else -- httpx reads them as a fragment and a query respectively.
    within = "/".join(quote(part, safe="") for part in parts[3:])
    item = await client.get(f"{GRAPH}/sites/{site_id}/drive/root:/{within}")
    if item.status_code != 200:
        raise GraphError(f"could not find {within!r}: {item.status_code}")
    return dict(item.json())


async def download(item: dict[str, Any], *, token: str) -> bytes:
    """The document's bytes as SharePoint last persisted them.

    Takes the same identity that resolved the item, so a user token is still the one
    fetching the content rather than only the metadata.

    ``/content`` answers 302 with a short-lived pre-authenticated URL. That URL is
    fetched without our bearer token: it carries its own authorisation, and sending
    ours to a storage host would put it somewhere other than Graph.
    """

    url = item.get("@microsoft.graph.downloadUrl")

    async with httpx.AsyncClient(timeout=180) as client:
        if not url:
            drive = item["parentReference"]["driveId"]
            redirect = await client.get(
                f"{GRAPH}/drives/{drive}/items/{item['id']}/content",
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=False,
            )
            url = redirect.headers.get("location")
            if not url:
                raise GraphError(
                    f"no download URL for {item.get('name')}: {redirect.status_code}"
                )
        response = await client.get(url, follow_redirects=True)

    if response.status_code != 200:
        raise GraphError(f"could not download {item.get('name')}: {response.status_code}")
    return response.content
