"""A Flat OPC package as a document ``docx-editor`` can edit.

Word's ``Range.getOoxml()`` hands an add-in a single XML document holding the same
parts a .docx contains. ``docx-editor`` works on a .docx on disk, unpacked into a
workspace. This is the adapter between the two, so the comment and tracked-change
knowledge lives in a maintained library rather than here.

Every part the document actually contains travels, binary ones included. Two do
not, and both were found the hard way, because Word rejects a package it dislikes
with ``GeneralException`` and no detail:

- ``[Content_Types].xml`` is not carried outward. Flat OPC states each part's type
  on the part itself and Word's own ``getOoxml()`` ships no such part, so
  ``to_docx`` builds one on the way in and ``from_docx`` leaves it out again.
- A part the content types never mention is not content. A file synced through
  OneDrive carries ``[trash]/*.dat`` entries that nothing references; inventing a
  type for them is what Word refused.
"""

import base64
import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from docx_editor import Document
from lxml import etree

from lib.services.docx.namespaces import PKG, qn

logger = logging.getLogger(__name__)

DRAFT_DETECTIVE = "Draft Detective"

_CONTENT_TYPES_PART = "[Content_Types].xml"
_DOCUMENT_ZIP_ENTRY = "word/document.xml"

_RELATIONSHIP_CONTENT_TYPE = (
    "application/vnd.openxmlformats-package.relationships+xml"
)
_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

# Word writes this ahead of the root and expects it back; without it the package
# is not recognised as a Word document.
_WORD_PROLOG = '<?mso-application progid="Word.Document"?>'


class FragmentError(Exception):
    """Raised when a package cannot be treated as an editable document."""


def _parts(markup: str) -> Iterator[tuple[str, str, bytes]]:
    """Every part as (zip entry name, declared content type, bytes).

    One traversal: the content type is needed to rebuild
    ``[Content_Types].xml`` and the bytes to write the entry, and reading the
    package twice for the two halves is a second parse of the same 60k.
    """

    root = etree.fromstring(markup.encode("utf-8"))
    for node in root.iterfind(qn("part", PKG)):
        name = (node.get(qn("name", PKG)) or "").lstrip("/")
        if not name:
            continue
        content_type = node.get(qn("contentType", PKG)) or ""
        xml_data = node.find(qn("xmlData", PKG))
        binary = node.find(qn("binaryData", PKG))
        if xml_data is not None and len(xml_data):
            payload = _part_xml(xml_data)
            if payload is not None:
                yield name, content_type, payload
        elif binary is not None and binary.text:
            yield name, content_type, base64.b64decode(binary.text)


def _part_xml(xml_data: Any) -> Optional[bytes]:
    """A part's XML, keeping anything that precedes its root element.

    SharePoint writes custom XML parts that open with a processing instruction, so
    the root element is not necessarily the first child. Taking the first child
    alone wrote out the instruction and dropped the document.
    """

    if not any(isinstance(child.tag, str) for child in xml_data):
        return None  # processing instructions only; there is no document here
    body = b"".join(etree.tostring(child) for child in xml_data)
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + body


def _content_types_part(types: dict[str, str]) -> bytes:
    """Build the ``[Content_Types].xml`` a .docx needs but Flat OPC does without.

    Word's ``getOoxml()`` carries each part's type in a ``pkg:contentType``
    attribute and ships no content-types part at all, so one has to be made here
    or the zip is not a document any reader will open. Every part gets an explicit
    Override, which is always correct and needs no reasoning about extensions.
    """

    overrides = "".join(
        f'<Override PartName="/{escape(name)}" ContentType="{escape(content_type)}"/>'
        for name, content_type in sorted(types.items())
        if not name.endswith(".rels")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CONTENT_TYPES_NS}">'
        f'<Default Extension="rels" ContentType="{_RELATIONSHIP_CONTENT_TYPE}"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{overrides}</Types>"
    ).encode("utf-8")


def to_docx(markup: str, path: Path) -> None:
    """Write a Flat OPC package out as the .docx the library expects."""

    written: set[str] = set()
    declared: dict[str, str] = {}
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, content_type, payload in _parts(markup):
            if name in written:  # a duplicated part name would corrupt the zip
                logger.warning("ignoring a repeated part in the package: %s", name)
                continue
            archive.writestr(name, payload)
            written.add(name)
            if content_type:
                declared[name] = content_type

        if _CONTENT_TYPES_PART not in written:
            archive.writestr(_CONTENT_TYPES_PART, _content_types_part(declared))

    if _DOCUMENT_ZIP_ENTRY not in written:
        raise FragmentError(
            f"the package has no {_DOCUMENT_ZIP_ENTRY} "
            f"({len(written)} parts received), so it is not a document"
        )


def _content_types(archive: ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    """The package's declared content types, as (by extension, by part name)."""

    by_extension: dict[str, str] = {}
    by_name: dict[str, str] = {}
    try:
        declaration = etree.fromstring(archive.read(_CONTENT_TYPES_PART))
    except (KeyError, etree.XMLSyntaxError) as error:
        logger.warning("could not read %s: %s", _CONTENT_TYPES_PART, error)
        return by_extension, by_name

    for node in declaration:
        tag = etree.QName(node).localname
        if tag == "Default":
            extension = (node.get("Extension") or "").lower()
            if extension:
                by_extension[extension] = node.get("ContentType") or ""
        elif tag == "Override":
            name = node.get("PartName") or ""
            if name:
                by_name[name] = node.get("ContentType") or ""
    return by_extension, by_name


def _content_type_of(
    name: str, by_extension: dict[str, str], by_name: dict[str, str]
) -> Optional[str]:
    """What this part declares itself to be, or None when it declares nothing.

    None means the part is not content: a .docx synced through OneDrive carries
    ``[trash]/*.dat`` entries that no relationship references and
    ``[Content_Types].xml`` never mentions. Inventing a type for those is what made
    Word reject the package, so they are reported as undeclared and dropped.
    """

    override = by_name.get("/" + name)
    if override:
        return override
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension == "rels":
        return by_extension.get("rels", _RELATIONSHIP_CONTENT_TYPE)
    return by_extension.get(extension)


def from_docx(path: Path) -> str:
    """Turn a .docx back into the Flat OPC an add-in can hand to ``insertOoxml``."""

    pieces: list[str] = []
    with ZipFile(path) as archive:
        by_extension, by_name = _content_types(archive)
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if name == _CONTENT_TYPES_PART:
                # Flat OPC states each part's type on the part itself, and Word's
                # own getOoxml() ships no content-types part. to_docx rebuilds one.
                continue
            content_type = _content_type_of(name, by_extension, by_name)
            if content_type is None:
                logger.info("leaving out %s: the package declares no type for it", name)
                continue
            payload = archive.read(name)
            attributes = f'pkg:name="/{escape(name)}" pkg:contentType="{escape(content_type)}"'
            if _is_xml(name, content_type):
                body = payload.decode("utf-8")
                # Flat OPC nests the part's root element directly; its own
                # declaration would be a second prolog inside one document.
                body = _without_declaration(body)
                pieces.append(
                    f"<pkg:part {attributes}><pkg:xmlData>{body}</pkg:xmlData></pkg:part>"
                )
            else:
                encoded = base64.b64encode(payload).decode("ascii")
                pieces.append(
                    f'<pkg:part {attributes} pkg:compression="store">'
                    f"<pkg:binaryData>{encoded}</pkg:binaryData></pkg:part>"
                )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        f"{_WORD_PROLOG}\r\n"
        f'<pkg:package xmlns:pkg="{PKG}">' + "".join(pieces) + "</pkg:package>"
    )


def _is_xml(name: str, content_type: str) -> bool:
    return name.endswith((".xml", ".rels")) or content_type.endswith("xml")


def _without_declaration(body: str) -> str:
    """Drop a part's own XML declaration, which cannot sit inside the package.

    The leading byte-order mark has to go first: Word writes parts with one, and
    ``str.lstrip()`` does not treat it as whitespace, so the declaration would go
    unrecognised and end up nested -- which makes the whole package unparseable.
    """

    stripped = body.lstrip("﻿").lstrip()
    if stripped.startswith("<?xml"):
        end = stripped.find("?>")
        if end >= 0:
            return stripped[end + 2 :].lstrip()
    return stripped


class Fragment:
    """An open document, with the means to hand it back as Flat OPC.

    Held rather than returned so the temporary directory and the library's
    workspace lock live exactly as long as the editing does.
    """

    def __init__(self, document: Document, work: Path) -> None:
        self.document = document
        self._work = work
        self._saves = 0

    def serialise(self) -> str:
        """Save what has been edited and return it as a Flat OPC package."""

        self._saves += 1
        # A distinct name per save: the library treats saving over its own source
        # as an in-place write and checks the file has not moved underneath it.
        out = self._work / f"edited-{self._saves}.docx"
        self.document.save(out)
        return from_docx(out)


@contextmanager
def editable(markup: str, author: str = DRAFT_DETECTIVE) -> Iterator[Fragment]:
    """Open a Flat OPC package for editing as ``author``.

    Attribution is the reason any of this goes through markup: anything created
    through Word's own API is authored as whoever is signed in, with no way to
    override it. The library takes the author once, at open, and stamps every
    comment and revision with it.

    The workspace lives in a directory of its own per call, so nothing is shared
    between requests and the library's lock can never contend with another.
    """

    work = Path(tempfile.mkdtemp(prefix="dd-word-"))
    try:
        source = work / "fragment.docx"
        # Both steps report the same way. Callers handle one failure type, and
        # markup that will not even parse used to escape as a raw lxml error and
        # surface as a 500 rather than as a package we could not use.
        try:
            to_docx(markup, source)
            document = Document.open(
                source, author=author, workspace_dir=str(work / "workspace")
            )
        except FragmentError:
            raise
        except Exception as error:
            raise FragmentError(
                f"the package could not be opened as a document: {error}"
            ) from error
        try:
            yield Fragment(document=document, work=work)
        finally:
            document.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
