"""The document open in Word, as the add-in's chat agent reads it.

The pane sends the .docx itself with a message (Office.js ``getFileAsync``), because the
add-in is the only party that can see a document mid-edit: SharePoint holds the last
saved copy, which was measured lagging a fresh edit by most of a minute, and an unsaved
document is nowhere else at all. It is read the way the Teams bot reads a downloaded
.docx (``lib/services/microsoft/graph/documents.py``), images included; the caller
stores those for the conversation (``_swap_images`` in
``lib/api/routers/microsoft/word_chat.py``).
"""

import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from lib.services.microsoft.graph.documents import LoadedDocument, read_docx

_DOCUMENT_PART = "word/document.xml"


class NotADocument(Exception):
    """Raised when what the pane sent is not a Word document."""


def _check(payload: bytes) -> None:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            if _DOCUMENT_PART not in archive.namelist():
                raise NotADocument(f"the file has no {_DOCUMENT_PART}")
    except BadZipFile as error:
        raise NotADocument("the file is not a .docx") from error


async def from_docx(payload: bytes, *, name: str, url: str) -> LoadedDocument:
    """The document as markdown with its comments and images. Raises ``NotADocument``."""

    _check(payload)
    work = Path(tempfile.mkdtemp(prefix="dd-pane-"))
    try:
        path = work / "document.docx"
        path.write_bytes(payload)
        read = await read_docx(path, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return LoadedDocument(
        name=name,
        url=url,
        markdown=read.markdown,
        comments=read.comments,
        size_bytes=len(payload),
        images=read.images,
    )
