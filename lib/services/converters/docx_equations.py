"""Convert the Word equations in a DOCX one at a time, before MarkItDown sees it.

MarkItDown converts every OMML equation in a document part in a single pass
and, when any one of them fails (0.1.5 cannot convert ``ln``), keeps the
original XML. mammoth then drops OMML, so a single unsupported equation erases
every equation from the markdown. Converting each equation on its own keeps
the ones that convert as LaTeX and the rest as their own characters.

The output mirrors MarkItDown's own replacement (an inline ``$...$`` run, a
``$$...$$`` paragraph per ``oMathPara``), so documents whose equations already
converted keep the same markdown and the same line numbers.
"""

import io
import logging
import zipfile
from xml.etree import ElementTree as ET

from lxml import etree  # type: ignore[import-untyped]
from markitdown.converter_utils.docx.math.omml import oMath2Latex

logger = logging.getLogger(__name__)

_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
# The parts MarkItDown pre-processes for math.
_EQUATION_PARTS = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def _equation_text(omath: etree._Element) -> str:
    """The equation's own characters, as Word stores them in ``m:t``."""
    return "".join(t.text or "" for t in omath.iter(f"{{{_M_NS}}}t"))


def _omath_to_latex(omath: etree._Element) -> str:
    """LaTeX for one ``m:oMath``, from MarkItDown's OMML converter."""
    return oMath2Latex(ET.fromstring(etree.tostring(omath))).latex


def _replacement_text(omath: etree._Element, block: bool) -> str:
    try:
        latex = _omath_to_latex(omath)
    except Exception as exc:
        text = _equation_text(omath)
        logger.warning(
            "Equation kept as plain text, LaTeX conversion failed (%s): %r",
            exc,
            text,
        )
        return text
    return f"$${latex}$$" if block else f"${latex}$"


def _text_run(text: str) -> etree._Element:
    run = etree.Element(f"{{{_W_NS}}}r")
    t = etree.SubElement(run, f"{{{_W_NS}}}t")
    t.text = text
    t.set(_XML_SPACE, "preserve")
    return run


def _replace(old: etree._Element, new: etree._Element) -> None:
    new.tail = old.tail
    parent = old.getparent()
    if parent is not None:
        parent.replace(old, new)


def _convert_part(xml: bytes) -> bytes | None:
    """Return the part with its equations replaced, or None when it has none."""
    root = etree.fromstring(xml, _PARSER)
    paras = list(root.iter(f"{{{_M_NS}}}oMathPara"))
    for para in paras:
        p = etree.Element(f"{{{_W_NS}}}p")
        for omath in para.iter(f"{{{_M_NS}}}oMath"):
            p.append(_text_run(_replacement_text(omath, block=True)))
        _replace(para, p)
    inline = list(root.iter(f"{{{_M_NS}}}oMath"))
    for omath in inline:
        _replace(omath, _text_run(_replacement_text(omath, block=False)))
    if not paras and not inline:
        return None
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def convert_docx_equations(docx_path: str) -> io.BytesIO | None:
    """Return a copy of the DOCX with every equation as text, or None if it has none."""
    with zipfile.ZipFile(docx_path) as zin:
        converted = {
            name: _convert_part(zin.read(name))
            for name in _EQUATION_PARTS
            if name in zin.namelist()
        }
        if not any(converted.values()):
            return None
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            zout.comment = zin.comment
            for item in zin.infolist():
                content = converted.get(item.filename) or zin.read(item.filename)
                zout.writestr(item, content)
    output.seek(0)
    return output
