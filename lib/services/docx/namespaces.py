"""OOXML namespaces and small helpers for reading WordprocessingML.

Shared by the modules that read the markup directly. Writing it is
``docx-editor``'s job, so the element builders that used to live here are gone.

The names match the prefixes used in the XML itself, which keeps call sites
readable when they mirror the markup's structure.
"""

from typing import Any

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
W16CID = "http://schemas.microsoft.com/office/word/2016/wordml/cid"
PKG = "http://schemas.microsoft.com/office/2006/xmlPackage"

# Spelled out where a test builds a package and "PKG" would read as a namespace
# prefix rather than the package format.
XML_PACKAGE = PKG


def qn(tag: str, namespace: str = W) -> str:
    """Qualified name for an element or attribute, e.g. ``qn("comment")``."""

    return f"{{{namespace}}}{tag}"


def w(tag: str) -> str:
    """Qualified name in the main WordprocessingML namespace."""

    return qn(tag, W)


def plain_text(node: Any) -> str:
    """All visible text under an element, ignoring deletions."""

    return "".join(item.text or "" for item in node.iter(w("t")))
