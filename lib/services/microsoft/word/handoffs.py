"""Comments and tracked changes asked for in Teams, applied later by the Word add-in.

The bot can read a document but never write one (see ``lib/models/microsoft_word_handoff``
for why), so a request for changes is stored here and picked up by the add-in when the
person who asked opens the document in Word.

**Places are quotes, not positions.** The bot reviewed the copy SharePoint had when it
was asked; by the time the add-in runs, the document may have moved on. A paragraph
number would silently point at the wrong place, whereas a quote is either still there or
is not, and an edit whose words are gone is reported back rather than misplaced.

**Recognising the document.** The add-in knows only the URL Word reports, and Word
reports different forms in different clients. Two keys cover them: the SharePoint
unique id (the GUID in ``sourcedoc=`` links and inside the item's eTag) and the
document's path. A handoff stores both, and a URL from the add-in is reduced to
whichever of them it carries.
"""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from urllib.parse import parse_qs, unquote, urlparse

from microsoft_agents.activity import ConversationReference
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, insert, or_, select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.microsoft_word_handoff import MicrosoftWordHandoff
from lib.services.microsoft.teams import bot

logger = logging.getLogger(__name__)

# Long enough for someone to get round to opening the document, short enough that
# review text quoted from a confidential document does not linger.
KEPT_FOR = timedelta(days=7)

# How much of a quote to show in Teams when saying it was not applied.
QUOTE_PREVIEW = 60

_GUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)


class HandoffComment(BaseModel):
    quote: str = Field(description="The exact words to attach the comment to")
    comment: str = Field(description="What Draft Detective says about them")


class HandoffEdit(BaseModel):
    quote: str = Field(description="The exact words to change")
    replacement: str = Field(description="What they become. Empty removes them.")


class HandoffItems(BaseModel):
    comments: list[HandoffComment] = Field(default_factory=list)
    edits: list[HandoffEdit] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.comments) + len(self.edits)


class Account(BaseModel):
    """A Microsoft account: its Entra object id, and its tenant when known.

    What a handoff is released to. Not an email address: a UPN and a mailbox can
    differ, and an address is not unique across sign-in providers.
    """

    oid: str
    tid: Optional[str] = None


class Requester(Account):
    """Who asked, as Graph and Teams know them."""

    upn: str


class HandoffView(BaseModel):
    """A pending handoff as the add-in sees it."""

    id: uuid.UUID
    document_name: str
    document_url: str
    items: HandoffItems
    created_at: datetime


class ItemOutcome(BaseModel):
    kind: Literal["comment", "edit"]
    quote: str
    applied: bool
    detail: str = ""


class HandoffOutcome(BaseModel):
    items: list[ItemOutcome] = Field(default_factory=list)

    @property
    def applied(self) -> int:
        return sum(1 for item in self.items if item.applied)


class FinishedHandoff(BaseModel):
    document_name: str
    reference: dict[str, Any]

    def conversation_reference(self) -> ConversationReference:
        return ConversationReference.model_validate(self.reference)


def _path_key(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if not parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path).rstrip("/").lower()
    if "/_layouts/" in path or path.startswith("/:"):
        return None  # a viewer or sharing link: the path is not the document's
    return f"path:{parsed.netloc.lower()}{path}"


def keys_for_url(url: str) -> set[str]:
    """The keys a URL from Word identifies its document by. Empty if it has none."""

    keys: set[str] = set()
    for value in parse_qs(urlparse(url).query).get("sourcedoc", []):
        if match := _GUID.search(unquote(value)):
            keys.add(f"guid:{match.group(0).lower()}")
    if path := _path_key(url):
        keys.add(path)
    return keys


def document_keys(item: dict[str, Any], library_url: Optional[str]) -> list[str]:
    """Every key the add-in might find this drive item under.

    ``library_url`` is the drive's own webUrl. The item's webUrl is usually a
    ``Doc.aspx?sourcedoc=`` viewer link for a Word document, so the path is rebuilt
    from the library and the item's place inside it.
    """

    keys: set[str] = set()
    for tag in (item.get("eTag"), item.get("cTag"), item.get("webUrl")):
        if tag and (match := _GUID.search(str(tag))):
            keys.add(f"guid:{match.group(0).lower()}")
    keys |= keys_for_url(str(item.get("webUrl") or ""))

    parent = str((item.get("parentReference") or {}).get("path") or "")
    if library_url and ":" in parent:
        folder = parent.split(":", 1)[1].strip("/")
        within = "/".join(part for part in (folder, str(item.get("name") or "")) if part)
        if path := _path_key(f"{library_url.rstrip('/')}/{within}"):
            keys.add(path)
    return sorted(keys)


def _owned_by(account: Account) -> Any:
    same_account = col(MicrosoftWordHandoff.requested_by_oid) == account.oid
    if not account.tid:
        return same_account
    # A tenant is compared when both sides know it; a handoff stored without one
    # still needs the object id to match.
    return and_(
        same_account,
        or_(
            col(MicrosoftWordHandoff.requested_by_tid).is_(None),
            col(MicrosoftWordHandoff.requested_by_tid) == account.tid,
        ),
    )


async def create(
    *,
    requester: Requester,
    document_name: str,
    document_url: str,
    keys: list[str],
    items: HandoffItems,
    reference: dict[str, Any],
) -> uuid.UUID:
    """Store a handoff, and sweep the ones past their time in the same transaction."""

    handoff_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with get_async_db_session() as session:
        await session.execute(
            insert(MicrosoftWordHandoff).values(
                id=handoff_id,
                requested_by_oid=requester.oid,
                requested_by_tid=requester.tid,
                requested_by_upn=requester.upn,
                document_name=document_name,
                document_url=document_url,
                document_keys=keys,
                items=items.model_dump(mode="json"),
                reference=reference,
                status="pending",
                created_at=now,
            )
        )
        await session.execute(
            delete(MicrosoftWordHandoff).where(
                col(MicrosoftWordHandoff.created_at) < now - KEPT_FOR
            )
        )
        await session.commit()
    logger.info("stored handoff %s with %s item(s)", handoff_id, items.count)
    return handoff_id


async def pending_for(account: Account) -> list[MicrosoftWordHandoff]:
    """Every handoff waiting for this person, newest first."""

    async with get_async_db_session() as session:
        rows = await session.execute(
            select(MicrosoftWordHandoff)
            .where(_owned_by(account))
            .where(col(MicrosoftWordHandoff.status) == "pending")
            .order_by(col(MicrosoftWordHandoff.created_at).desc())
        )
        return list(rows.scalars().all())


def split_by_document(
    handoffs: list[MicrosoftWordHandoff], url: str
) -> tuple[list[HandoffView], list[HandoffView]]:
    """The handoffs for the document at ``url``, and the rest.

    The rest are returned too, so that a URL form we failed to recognise shows up as
    "you have suggestions for another document" rather than as nothing at all.
    """

    wanted = keys_for_url(url)
    here: list[HandoffView] = []
    elsewhere: list[HandoffView] = []
    for row in handoffs:
        view = HandoffView(
            id=row.id,
            document_name=row.document_name,
            document_url=row.document_url,
            items=HandoffItems.model_validate(row.items),
            created_at=row.created_at,
        )
        (here if wanted & set(row.document_keys) else elsewhere).append(view)
    return here, elsewhere


async def finish(
    handoff_id: uuid.UUID,
    account: Account,
    status: Literal["applied", "dismissed"],
    outcome: Optional[HandoffOutcome] = None,
) -> Optional[FinishedHandoff]:
    """Close a pending handoff, once. ``None`` if it is not theirs or already closed.

    One conditional UPDATE, so two panes reporting the same handoff cannot both get a
    message posted into Teams.
    """

    async with get_async_db_session() as session:
        row = (
            await session.execute(
                update(MicrosoftWordHandoff)
                .where(col(MicrosoftWordHandoff.id) == handoff_id)
                .where(_owned_by(account))
                .where(col(MicrosoftWordHandoff.status) == "pending")
                .values(
                    status=status,
                    outcome=outcome.model_dump(mode="json") if outcome else None,
                    finished_at=datetime.now(timezone.utc),
                )
                .returning(
                    col(MicrosoftWordHandoff.document_name),
                    col(MicrosoftWordHandoff.reference),
                )
            )
        ).first()
        await session.commit()
    if row is None:
        return None
    return FinishedHandoff(document_name=row[0], reference=row[1])


async def report_applied(
    handoff_id: uuid.UUID, account: Account, outcome: HandoffOutcome
) -> bool:
    """Close a handoff the add-in has written, and say how it went in Teams.

    False if it is not theirs or already closed, in which case nothing is posted.
    """

    finished = await finish(handoff_id, account, "applied", outcome)
    if finished is None:
        return False
    await bot.post_later(finished.conversation_reference(), report(finished, outcome))
    return True


def report(finished: FinishedHandoff, outcome: HandoffOutcome) -> str:
    """The message posted into Teams once the add-in has applied a handoff."""

    total = len(outcome.items)
    lines = [
        f"Applied to **{finished.document_name}** in Word: "
        f"{outcome.applied} of {total} suggestion(s)."
    ]
    missed = [item for item in outcome.items if not item.applied]
    if missed:
        lines.append("")
        lines.append("Not applied:")
        for item in missed:
            quote = " ".join(item.quote.split())
            if len(quote) > QUOTE_PREVIEW:
                quote = quote[:QUOTE_PREVIEW].rstrip() + "…"
            reason = f" ({item.detail})" if item.detail else ""
            lines.append(f"- {item.kind} on “{quote}”{reason}")
    return "\n".join(lines)
