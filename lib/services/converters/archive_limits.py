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
# keeping one conversion well under a gigabyte.
MAX_XML_BYTES = 64 * 1024 * 1024

# Media is held about as large as it is stored, so the bound for the whole
# archive is what an honest upload may already carry (the tus upload limit).
MAX_EXPANDED_BYTES = 500 * 1024 * 1024

_XML_SUFFIXES = (".xml", ".rels", ".vml")


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
    except zipfile.BadZipFile:
        return

    xml_bytes = sum(m.file_size for m in members if m.filename.endswith(_XML_SUFFIXES))
    expanded_bytes = sum(m.file_size for m in members)
    if xml_bytes > MAX_XML_BYTES or expanded_bytes > MAX_EXPANDED_BYTES:
        raise ArchiveTooLargeError(
            f"The document expands to {expanded_bytes} bytes "
            f"({xml_bytes} of them XML), more than can be converted."
        )
