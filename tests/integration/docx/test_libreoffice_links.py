"""LibreOffice never loads what an uploaded document links to — requires LibreOffice.

A Word file can link an image by URL instead of embedding it. Unguarded,
importing a ``.doc`` makes LibreOffice request that URL from the server, and a
PDF export draws a ``file://`` image into the output. Each test runs the attack
against a server or a file on this machine only.
"""

import asyncio
import io
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from PIL import Image

from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.converters.libreoffice_profile import locked_down_profile

_SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")

pytestmark = pytest.mark.skipif(_SOFFICE is None, reason="LibreOffice not installed")

_PDF_IMAGE_OBJECT = 3  # FPDF_PAGEOBJ_IMAGE


class _Recorder(BaseHTTPRequestHandler):
    """Answers every request with a small PNG and remembers its path."""

    paths: list[str]

    def _answer(self) -> None:
        self.paths.append(self.path)
        body = _png_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_OPTIONS = _answer

    def log_message(self, format: str, *args: object) -> None:
        pass


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def server() -> Iterator[tuple[str, list[str]]]:
    paths: list[str] = []
    handler = type("Handler", (_Recorder,), {"paths": paths})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", paths
    finally:
        httpd.shutdown()
        httpd.server_close()


def _docx_linking_image(path: Path, target: str) -> Path:
    """A document whose only picture is linked to ``target``, not embedded."""
    document = Document()
    document.add_paragraph("A document with a linked picture.")
    link = document.part.relate_to(target, RT.IMAGE, is_external=True)
    xml = (
        f"<w:p {nsdecls('w', 'wp', 'a', 'r', 'pic')}><w:r><w:drawing><wp:inline>"
        '<wp:extent cx="914400" cy="914400"/><wp:docPr id="1" name="linked"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="linked"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:link="{link}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm>'
        '<a:prstGeom prst="rect"/></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )
    document.element.body.get_or_add_sectPr().addprevious(parse_xml(xml))
    document.save(str(path))
    return path


def _soffice(*args: str, profile: str) -> None:
    assert _SOFFICE is not None
    subprocess.run(
        [_SOFFICE, "--headless", profile, *args],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _make_doc(docx: Path, workdir: Path) -> Path:
    """Save ``docx`` as a Word 97 binary; the save itself does not follow links."""
    _soffice(
        "--convert-to",
        "doc",
        "--outdir",
        str(docx.parent),
        str(docx),
        profile=f"-env:UserInstallation={(workdir / 'make-doc').as_uri()}",
    )
    return docx.with_suffix(".doc")


@pytest.mark.asyncio
async def test_doc_import_does_not_request_a_linked_image(
    tmp_path, server, monkeypatch
):
    base_url, paths = server
    # A deploy may exempt exactly its internal addresses from its egress proxy.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    source = _docx_linking_image(tmp_path / "upload.docx", f"{base_url}/internal")
    doc = _make_doc(source, tmp_path)
    source.unlink()
    assert paths == []

    converted = await docx_preprocessor.convert_doc_to_docx(str(doc))

    assert Path(converted).exists()
    assert paths == []


@pytest.mark.asyncio
async def test_pdf_export_does_not_draw_a_local_linked_image(tmp_path):
    secret = tmp_path / "on-the-server.png"
    Image.new("RGB", (40, 40), (0, 0, 255)).save(secret)
    docx = _docx_linking_image(tmp_path / "upload.docx", secret.as_uri())
    profile = locked_down_profile(tmp_path / "profile")

    await asyncio.to_thread(
        _soffice,
        "--convert-to",
        "pdf",
        "--outdir",
        str(tmp_path),
        str(docx),
        profile=profile,
    )

    pdf = pdfium.PdfDocument(str(tmp_path / "upload.pdf"))
    try:
        kinds = [obj.type for obj in pdf[0].get_objects()]
    finally:
        pdf.close()
    assert _PDF_IMAGE_OBJECT not in kinds
