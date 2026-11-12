"""A SharePoint document, loaded as markdown.

Two readers, because neither does both jobs. **markitdown** produces the body, the same
converter the rest of the app uses for a main document -- headings, tables and emphasis
survive, where a paragraph-by-paragraph read flattens them into indistinguishable
strings. **docx-editor** produces the comments, which markitdown does not extract.

The body is converted the way the web app converts a project's main document
(``convert_docx``): native charts and metafile pictures are rendered to images first,
and every image is saved to disk and referenced from the markdown as
``draftdetective://{id}``, for ``view_image``. Saving the ``files`` rows that make those
ids resolvable is the caller's: it knows which conversation owns them.

Read-only. Writing back is refused by SharePoint with 423 while anyone has the
document open, so it is not offered here at all.
"""

import asyncio
import logging
import shutil
import tempfile
import time
from pathlib import Path

from docx_editor import Document
from pydantic import BaseModel, Field

from lib.services.files.conversion import convert_docx
from lib.services.files.image_extraction import ExtractedImage, extract_data_uri_images
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
    last_modified: str | None = None
    images: list[ExtractedImage] = Field(
        default_factory=list,
        description="The images the markdown references, saved but not yet owned",
    )

    @property
    def lines(self) -> int:
        """How long the document is, in the units the agent's tools count in."""

        return len(self.markdown.splitlines())


def read_comments(path: Path, work: Path) -> list[tuple[str, str]]:
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


class ReadDocx(BaseModel):
    markdown: str
    comments: list[tuple[str, str]]
    images: list[ExtractedImage]


async def read_docx(path: Path, work: Path) -> ReadDocx:
    """A .docx on disk as markdown with its images, plus its comments.

    ``work`` is scratch space. Shared with the add-in's chat, which reads the .docx the
    pane sends (``lib/services/microsoft/word/pane_document.py``).
    """

    start = time.perf_counter()
    markdown, display_sizes = await convert_docx(str(path), keep_data_uris=True)
    extraction = await extract_data_uri_images(markdown, display_sizes)
    # docx-editor is synchronous and unzips into a workspace, so it does not belong on
    # the event loop.
    comments = await asyncio.to_thread(read_comments, path, work)
    logger.info(
        "read a .docx: %s images, %.1f s",
        len(extraction.images),
        time.perf_counter() - start,
    )
    return ReadDocx(
        markdown=extraction.markdown, comments=comments, images=extraction.images
    )


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
        read = await read_docx(path, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return LoadedDocument(
        name=str(item.get("name") or "document.docx"),
        url=url,
        markdown=read.markdown,
        comments=read.comments,
        last_modified=item.get("lastModifiedDateTime"),
        images=read.images,
    )
