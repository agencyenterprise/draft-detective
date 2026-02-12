"""Helpers for low-level DOCX XML and package editing."""

import os
import shutil
import tempfile
from typing import Any, Dict, Optional
import zipfile
from pathlib import Path

from lxml import etree
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

CUSTOM_PROPERTIES_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
CUSTOM_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.custom-properties+xml"
)
CUSTOM_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_2012_WORDML_NAMESPACE_URI = "http://schemas.microsoft.com/office/word/2012/wordml"


def _set_sdt_prop(sdt_pr: etree._Element, tag: str, value: Optional[str]) -> None:
    qualified_tag = tag
    if tag.startswith("{"):
        qualified_tag = tag
    elif ":" in tag:
        prefix, local_name = tag.split(":", 1)
        namespace_uri = sdt_pr.nsmap.get(prefix)
        if namespace_uri:
            qualified_tag = f"{{{namespace_uri}}}{local_name}"
        else:
            qualified_tag = qn(tag)
    element = sdt_pr.find(qualified_tag)
    if value:
        if element is None:
            try:
                element = OxmlElement(tag)
            except (KeyError, ValueError):
                element = etree.Element(qualified_tag)
            sdt_pr.append(element)
        element.set(qn("w:val"), value)
    elif element is not None:
        sdt_pr.remove(element)


def _get_namespace_tag(
    element: etree._Element, namespace_uri: str, local_name: str
) -> str:
    for prefix, uri in element.nsmap.items():
        if uri == namespace_uri and prefix:
            return f"{prefix}:{local_name}"
    return f"{{{namespace_uri}}}{local_name}"


def wrap_paragraph_with_content_control(
    paragraph: Paragraph,
    tag_value: str,
    title: str,
    color_hex: Optional[str],
) -> None:
    """Wrap a docx lib Paragraph object with a content control."""
    # python-docx exposes no public API for this XML-level operation.
    # pylint: disable=protected-access
    paragraph_element = paragraph._p
    parent = paragraph_element.getparent()
    if parent is None:
        return

    sdt = None
    if parent.tag == qn("w:sdtContent"):
        potential_sdt = parent.getparent()
        if potential_sdt is not None and potential_sdt.tag == qn("w:sdt"):
            sdt = potential_sdt

    if sdt is None:
        sdt = OxmlElement("w:sdt")
        sdt_pr = OxmlElement("w:sdtPr")
        sdt.append(sdt_pr)
        sdt_content = OxmlElement("w:sdtContent")
        sdt.append(sdt_content)

        parent_index = parent.index(paragraph_element)
        parent.remove(paragraph_element)
        sdt_content.append(paragraph_element)
        parent.insert(parent_index, sdt)
    else:
        sdt_pr = sdt.find(qn("w:sdtPr"))
        if sdt_pr is None:
            sdt_pr = OxmlElement("w:sdtPr")
            sdt.insert(0, sdt_pr)

    _set_sdt_prop(sdt_pr, "w:tag", tag_value)
    _set_sdt_prop(sdt_pr, "w:alias", title)
    _set_sdt_prop(
        sdt_pr,
        _get_namespace_tag(sdt_pr, W_2012_WORDML_NAMESPACE_URI, "color"),
        color_hex,
    )
    _set_sdt_prop(sdt_pr, "w:appearance", "boundingBox")


def _next_relationship_id(relationships_root: etree._Element) -> str:
    existing_ids = []
    relationship_tag = f"{{{PACKAGE_REL_NS}}}Relationship"
    for rel in relationships_root.findall(relationship_tag):
        rel_id = rel.get("Id", "")
        if rel_id.startswith("rId"):
            suffix = rel_id[3:]
            if suffix.isdigit():
                existing_ids.append(int(suffix))
    return f"rId{max(existing_ids, default=0) + 1}"


def _ensure_custom_properties_relationship(temp_dir: str) -> None:
    rels_dir = os.path.join(temp_dir, "_rels")
    os.makedirs(rels_dir, exist_ok=True)
    rels_path = os.path.join(rels_dir, ".rels")

    relationship_tag = f"{{{PACKAGE_REL_NS}}}Relationship"

    if os.path.exists(rels_path):
        rels_tree = etree.parse(rels_path)
        rels_root = rels_tree.getroot()
    else:
        rels_root = etree.Element(
            f"{{{PACKAGE_REL_NS}}}Relationships", nsmap={None: PACKAGE_REL_NS}
        )
        rels_tree = etree.ElementTree(rels_root)

    for rel in rels_root.findall(relationship_tag):
        if (
            rel.get("Type") == CUSTOM_PROPERTIES_REL_TYPE
            and rel.get("Target") == "docProps/custom.xml"
        ):
            return

    etree.SubElement(
        rels_root,
        relationship_tag,
        {
            "Id": _next_relationship_id(rels_root),
            "Type": CUSTOM_PROPERTIES_REL_TYPE,
            "Target": "docProps/custom.xml",
        },
    )
    rels_tree.write(
        rels_path,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )


def _ensure_custom_properties_content_type(temp_dir: str) -> None:
    content_types_path = os.path.join(temp_dir, "[Content_Types].xml")
    ct_tree = etree.parse(content_types_path)
    ct_root = ct_tree.getroot()

    override_tag = f"{{{CONTENT_TYPES_NS}}}Override"

    for child in ct_root.findall(override_tag):
        if child.get("PartName") == "/docProps/custom.xml":
            return

    etree.SubElement(
        ct_root,
        override_tag,
        {
            "PartName": "/docProps/custom.xml",
            "ContentType": CUSTOM_PROPERTIES_CONTENT_TYPE,
        },
    )
    ct_tree.write(
        content_types_path,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )


def add_custom_properties_to_docx(
    docx_path: str | Path,
    properties: Dict[str, Any],
    output_path: str | Path | None = None,
) -> None:
    """Add or replace custom properties in a DOCX package."""
    source_path = str(docx_path)
    destination_path = str(output_path or docx_path)
    temp_dir = tempfile.mkdtemp()

    try:
        with zipfile.ZipFile(source_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        docprops_dir = os.path.join(temp_dir, "docProps")
        os.makedirs(docprops_dir, exist_ok=True)
        custom_xml_path = os.path.join(docprops_dir, "custom.xml")

        if os.path.exists(custom_xml_path):
            tree = etree.parse(custom_xml_path)
            root = tree.getroot()
        else:
            root = etree.Element(
                f"{{{CUSTOM_NS}}}Properties",
                nsmap={None: CUSTOM_NS, "vt": VT_NS},
            )
            tree = etree.ElementTree(root)

        existing_pids = [
            int(p.get("pid"))
            for p in root.findall(f"{{{CUSTOM_NS}}}property")
            if p.get("pid") is not None
        ]
        next_pid = max(existing_pids, default=1) + 1

        for prop in root.findall(f"{{{CUSTOM_NS}}}property"):
            if prop.get("name") in properties:
                root.remove(prop)

        for prop_name, prop_value in properties.items():
            prop_el = etree.SubElement(
                root,
                f"{{{CUSTOM_NS}}}property",
                {
                    "fmtid": "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}",
                    "pid": str(next_pid),
                    "name": prop_name,
                },
            )

            val_el = etree.SubElement(prop_el, f"{{{VT_NS}}}lpwstr")
            val_el.text = str(prop_value) if prop_value is not None else ""
            next_pid += 1

        tree.write(
            custom_xml_path,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

        _ensure_custom_properties_content_type(temp_dir)
        _ensure_custom_properties_relationship(temp_dir)

        with zipfile.ZipFile(destination_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for foldername, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    filepath = os.path.join(foldername, filename)
                    arcname = os.path.relpath(filepath, temp_dir)
                    zip_out.write(filepath, arcname)
    finally:
        shutil.rmtree(temp_dir)
