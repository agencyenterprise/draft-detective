"""Offering comments and tracked changes from Teams, to be applied in Word.

The Teams agent cannot write to a document, so asked to fix or annotate one it stores
what it would do with this tool, and the Word add-in applies it when the person who
asked opens the document. ``lib/services/microsoft/word/handoffs.py`` explains the
storage; this is the agent-facing side.

Built per run like the SharePoint tools: the asker's token and the conversation to
report back to are closed over, never parameters the model could change.
"""

import logging
from typing import Any, Optional

from langchain.tools import BaseTool, tool

from lib.services.microsoft.graph import client
from lib.services.microsoft.graph.client import GraphError, redacted
from lib.services.microsoft.word import handoffs
from lib.services.microsoft.word.handoffs import (
    HandoffComment,
    HandoffEdit,
    HandoffItems,
    Requester,
)

logger = logging.getLogger(__name__)

# A ceiling on one handoff, so a runaway review cannot bury the margin. Each item is a
# paragraph read and write in Word, so this also bounds how long Apply takes.
MAX_COMMENTS = 100
MAX_EDITS = 100
MIN_QUOTE_CHARS = 3


def usable_items(
    comments: list[HandoffComment], edits: list[HandoffEdit]
) -> HandoffItems:
    """Drop what cannot be applied, and cap the rest.

    An edit that changes nothing is dropped, and of two edits on the same words only
    the first can land: the first moves them into a deletion the second cannot find.
    """

    kept_comments = [
        item
        for item in comments
        if len(item.quote.strip()) >= MIN_QUOTE_CHARS and item.comment.strip()
    ]
    kept_edits: list[HandoffEdit] = []
    seen: set[str] = set()
    for edit in edits:
        words = " ".join(edit.quote.split()).lower()
        if len(words) < MIN_QUOTE_CHARS or edit.replacement.strip() == edit.quote.strip():
            continue
        if words in seen:
            continue
        seen.add(words)
        kept_edits.append(edit)
    return HandoffItems(
        comments=kept_comments[:MAX_COMMENTS], edits=kept_edits[:MAX_EDITS]
    )


def tenant_of(reference: dict[str, Any]) -> Optional[str]:
    """The asker's tenant, from the Teams conversation they asked in."""

    tenant = (reference.get("conversation") or {}).get("tenantId")
    return str(tenant) if tenant else None


def offer_changes_for(token: str, reference: dict[str, Any]) -> BaseTool:
    """The tool, storing handoffs as whoever ``token`` belongs to."""

    @tool()
    async def offer_changes(
        url: str,
        comments: list[HandoffComment],
        edits: list[HandoffEdit],
    ) -> str:
        """
        Offer comments and tracked changes for a document, to be applied in Word.

        You cannot write to the document from here. This saves what you would add, and
        the Draft Detective add-in writes it into the document — as comments and
        tracked changes authored by Draft Detective — when the person asking opens it in
        Word. Only they can apply it.

        Each item is found in the document by its quote, so a quote must be the
        document's exact words: copied verbatim, as plain text with no markdown (no
        `**`, `#`, `|` or backslashes), within a single paragraph, and long enough to
        appear only once in the whole document.

        Args:
            url: The document's SharePoint link.
            comments: Points to raise, each attached to the words it is about.
            edits: Wording changes, each replacing the quoted words. Keep the quote to
                the smallest span that changes; an empty replacement deletes it.

        Returns:
            What was saved, or why nothing was.
        """

        items = usable_items(comments, edits)
        if not items.count:
            return "Nothing was saved: none of those comments or edits could be applied."

        try:
            item = await client.resolve(url, token=token)
            drive = str((item.get("parentReference") or {}).get("driveId") or "")
            library = await client.library_url(drive, token=token) if drive else None
            person = await client.me(token=token)
        except GraphError as error:
            logger.info("could not offer changes for %s: %s", redacted(url), error)
            return f"I could not save changes for that document: {error}"

        keys = handoffs.document_keys(item, library)
        oid = str(person.get("id") or "")
        upn = str(person.get("userPrincipalName") or person.get("mail") or "")
        if not keys or not oid:
            return "I could not save changes for that document: it could not be identified."

        name = str(item.get("name") or "the document")
        await handoffs.create(
            requester=Requester(oid=oid, tid=tenant_of(reference), upn=upn),
            document_name=name,
            document_url=str(item.get("webUrl") or url),
            keys=keys,
            items=items,
            reference=reference,
        )
        return (
            f"Saved {len(items.comments)} comment(s) and {len(items.edits)} tracked "
            f"change(s) for '{name}'. They are written into the document when the "
            "person who asked opens it in Word with the Draft Detective add-in and "
            "chooses Apply. Tell them that, and say briefly what you offered."
        )

    return offer_changes
