"""A SharePoint document, loaded as markdown.

The backend holds a real .docx here rather than the Flat OPC an add-in sends, so both
readers below open it directly and none of the adapter in
``lib/services/microsoft/word/word_package.py`` is involved. That is the one clear
simplification of loading documents server-side.

Two readers, because neither does both jobs. **markitdown** produces the body, the same
converter the rest of the app uses for a main document -- headings, tables and emphasis
survive, where a paragraph-by-paragraph read flattens them into indistinguishable
strings. **docx-editor** produces the comments, which markitdown does not extract.

Read-only. Writing back is refused by SharePoint with 423 while anyone has the
document open, so it is not offered here at all.
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from docx_editor import Document
from pydantic import BaseModel, Field

from lib.services.converters.base import convert_to_markdown
from lib.services.microsoft.graph import client

logger = logging.getLogger(__name__)


class LoadedDocument(BaseModel):
    """What the agent needs to answer a question about a document."""

    name: str
    url: str
    markdown: str = Field(
        description="The document as markdown, with its structure intact"
    )
    comments: list[tuple[str, str]] = Field(
        default_factory=list, description="(author, text), threads and replies alike"
    )
    last_modified: Optional[str] = None
    size_bytes: int = 0

    @property
    def lines(self) -> int:
        """How long the document is, in the units the agent's tools count in."""

        return len(self.markdown.splitlines())


def _read_comments(path: Path, work: Path) -> list[tuple[str, str]]:
    """Comments and their replies, flattened, via docx-editor on a real file."""

    doc = Document.open(path, author="Draft Detective", workspace_dir=str(work / "ws"))
    try:
        comments: list[tuple[str, str]] = []
        for comment in doc.list_comments():
            comments.append((comment.author, comment.text))
            for reply in comment.replies:
                comments.append((reply.author, reply.text))
    finally:
        doc.close()
    return comments


async def load(url: str, *, token: str) -> LoadedDocument:
    """Load a document by its SharePoint URL, as whoever ``token`` belongs to.

    The identity is required rather than defaulted: Graph refuses a document that person
    cannot open, and that refusal *is* the permission check.

    Raises ``client.GraphError`` when Graph will not serve it -- including when it will
    not serve it *to this person*.
    """

    item = await client.resolve(url, token=token)
    payload = await client.download(item, token=token)
    logger.info(
        "loaded %s (%s bytes, modified %s)",
        item.get("name"),
        len(payload),
        item.get("lastModifiedDateTime"),
    )

    work = Path(tempfile.mkdtemp(prefix="dd-graph-"))
    try:
        path = work / "document.docx"
        path.write_bytes(payload)
        markdown = await convert_to_markdown(str(path), converter="markitdown")
        # docx-editor is synchronous and unzips into a workspace, so it does not
        # belong on the event loop.
        comments = await asyncio.to_thread(_read_comments, path, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return LoadedDocument(
        name=str(item.get("name") or "document.docx"),
        url=url,
        markdown=markdown,
        comments=comments,
        last_modified=item.get("lastModifiedDateTime"),
        size_bytes=len(payload),
    )
