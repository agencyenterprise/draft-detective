"""Refuse zip-based documents that expand far past what an upload may hold.

A .docx (like .pptx and .xlsx) is a zip archive, and every reader we use
(mammoth via markitdown, python-docx, lxml) inflates its parts into memory
whole. Deflate packs repetitive XML about a thousand to one, so a 1 MB upload
can declare a 1 GB ``word/document.xml``; converting that took 7.8 GB of
memory, against a 2 GiB API pod. The check reads only the central directory,
so it costs nothing on an honest document.

The sizes it sums are the ones each member declares. Python's ``zipfile``
stops inflating a member at its declared size and fails the CRC check past
it, so an archive that understates them cannot get more through the readers
than it declared.
"""

import zipfile

# XML is what inflates hardest once parsed: about eight times its own size in
# memory across the conversion. The largest document.xml among the documents
# we have seen is under 4 MiB, so this leaves wide room for long reports while
# keeping one conversion well under a gigabyte. A part counts as XML by its
# first bytes, never by its name or folder: readers find the main part through
# ``_rels/.rels``, so a body named ``document.dat`` or ``media/image1.png``
# still gets parsed.
MAX_XML_BYTES = 64 * 1024 * 1024

# Media is held about as large as it is stored, so the bound for the whole
# archive is what an honest upload may already carry (the tus upload limit).
MAX_EXPANDED_BYTES = 500 * 1024 * 1024

# A Word document holds tens to a few hundred parts. The cap bounds the
# per-part reads below, which an upload of tiny parts could otherwise stretch.
MAX_MEMBERS = 10_000

# How an XML document may begin: markup, whitespace, a byte-order mark, or the
# NUL half of a UTF-16 character. A part that begins otherwise (a PNG, a JPEG,
# an EMF, an embedded font) cannot be parsed as XML, so it is held only to the
# archive's total.
_XML_FIRST_BYTES = frozenset(b"< \t\r\n\x00")
_BYTE_ORDER_MARKS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")


class ArchiveTooLargeError(ValueError):
    """The document expands to more than it may be converted from."""


def check_archive_expansion(path: str) -> None:
    """Raise ``ArchiveTooLargeError`` when the zip at ``path`` expands too far.

    Files that are not zip archives (PDF, legacy .doc, plain text) pass
    untouched; a damaged archive is left for the reader to report.
    """
    if not zipfile.is_zipfile(path):
        return
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            # The declared sizes alone settle the cheap cases, before any part
            # is opened.
            expanded_bytes = sum(m.file_size for m in members)
            if len(members) > MAX_MEMBERS or expanded_bytes > MAX_EXPANDED_BYTES:
                raise ArchiveTooLargeError(
                    f"The document holds {len(members)} parts expanding to "
                    f"{expanded_bytes} bytes, more than can be converted."
                )
            xml_bytes = sum(m.file_size for m in members if _may_be_xml(archive, m))
    except zipfile.BadZipFile:
        return

    if xml_bytes > MAX_XML_BYTES:
        raise ArchiveTooLargeError(
            f"The document expands to {expanded_bytes} bytes "
            f"({xml_bytes} of them XML), more than can be converted."
        )


def _may_be_xml(archive: zipfile.ZipFile, member: zipfile.ZipInfo) -> bool:
    """Whether a reader could parse ``member`` as XML, judged by its first bytes.

    Inflating three bytes costs next to nothing whatever the member declares.
    A member that cannot be read counts as XML, so it is never waved through.
    """
    try:
        with archive.open(member) as part:
            head = part.read(3)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError):
        return True
    return not head or head[0] in _XML_FIRST_BYTES or head.startswith(_BYTE_ORDER_MARKS)
